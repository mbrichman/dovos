"""
Background worker for processing embedding generation jobs.

This worker:
- Uses FOR UPDATE SKIP LOCKED for concurrent processing
- Implements exponential backoff retry logic
- Generates embeddings using sentence-transformers
- Handles job failures gracefully
- Provides comprehensive logging and metrics
"""

import os
import sys
import time
import signal
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import threading
from contextlib import contextmanager

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from db.repositories.unit_of_work import get_unit_of_work
from db.models.models import Job, Message, MessageEmbedding
from config import EMBEDDING_MODEL, EMBEDDING_DIM

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Handles embedding generation using sentence-transformers."""
    
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model_name = model_name
        self._model = None
        
    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"✅ Model loaded successfully")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for the given text."""
        try:
            # Generate embedding
            embedding = self.model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise


class EmbeddingWorker:
    """
    Background worker that processes embedding generation jobs from PostgreSQL queue.
    """
    
    def __init__(self, 
                 worker_id: str = None,
                 max_jobs_per_batch: int = 5,
                 poll_interval_seconds: int = 2,
                 max_retries: int = 3):
        self.worker_id = worker_id or f"worker-{os.getpid()}-{threading.get_ident()}"
        self.max_jobs_per_batch = max_jobs_per_batch
        self.poll_interval_seconds = poll_interval_seconds
        self.max_retries = max_retries
        self.running = False
        self.embedding_generator = EmbeddingGenerator()
        
        # Stats
        self.stats = {
            'jobs_processed': 0,
            'jobs_successful': 0,
            'jobs_failed': 0,
            'start_time': None,
            'last_job_time': None
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        
    def start(self):
        """Start the worker loop."""
        self.running = True
        self.stats['start_time'] = datetime.utcnow()
        
        logger.info(f"🚀 Starting embedding worker {self.worker_id}")
        logger.info(f"   Max jobs per batch: {self.max_jobs_per_batch}")
        logger.info(f"   Poll interval: {self.poll_interval_seconds}s")
        logger.info(f"   Max retries: {self.max_retries}")
        
        try:
            while self.running:
                jobs_processed = self._process_batch()
                
                if jobs_processed == 0:
                    # No jobs found, wait before polling again
                    time.sleep(self.poll_interval_seconds)
                else:
                    # Jobs were processed, check for more immediately
                    self.stats['last_job_time'] = datetime.utcnow()
                    
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
        except Exception as e:
            logger.error(f"Worker crashed: {e}")
            raise
        finally:
            self._log_final_stats()
            
    def stop(self):
        """Stop the worker gracefully."""
        self.running = False
        logger.info(f"🛑 Stopping worker {self.worker_id}")
        
    def _process_batch(self) -> int:
        """Process a batch of jobs. Returns number of jobs processed."""
        jobs_processed = 0
        
        try:
            with get_unit_of_work() as uow:
                # Dequeue jobs using FOR UPDATE SKIP LOCKED
                jobs = self._dequeue_jobs(uow, self.max_jobs_per_batch)
                
                for job in jobs:
                    if not self.running:
                        break
                        
                    success = self._process_job(uow, job)
                    jobs_processed += 1
                    self.stats['jobs_processed'] += 1
                    
                    if success:
                        self.stats['jobs_successful'] += 1
                    else:
                        self.stats['jobs_failed'] += 1
                        
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            
        return jobs_processed
    
    def _dequeue_jobs(self, uow, limit: int) -> List[Job]:
        """Dequeue jobs from the queue safely using FOR UPDATE SKIP LOCKED."""
        try:
            jobs = []
            for _ in range(limit):
                job = uow.jobs.dequeue_next(
                    kinds=['generate_embedding'],
                    max_attempts=self.max_retries
                )
                if job:
                    jobs.append(job)
                else:
                    break  # No more jobs available
            return jobs
        except Exception as e:
            logger.error(f"Failed to dequeue jobs: {e}")
            return []
    
    def _process_job(self, uow, job: Job) -> bool:
        """Process a single embedding job. Returns True if successful."""
        job_id = job.id
        payload = job.payload
        
        logger.info(f"🔄 Processing job {job_id}: {payload.get('message_id', 'unknown')}")
        
        try:
            # Validate payload
            if not self._validate_job_payload(payload):
                logger.error(f"Invalid job payload for job {job_id}: {payload}")
                uow.jobs.mark_failed(job_id)
                return False
            
            # Get the message
            message_id = payload['message_id']
            message = uow.messages.get_by_id(message_id)
            
            if not message:
                logger.error(f"Message {message_id} not found for job {job_id}")
                uow.jobs.mark_failed(job_id)
                return False
            
            # Generate embedding
            embedding_vector = self.embedding_generator.generate_embedding(message.content)
            
            # Save or update the embedding
            existing_embedding = uow.embeddings.get_by_message_id(message_id)
            
            if existing_embedding:
                # Update existing embedding using the create_or_update method
                uow.embeddings.create_or_update(
                    message_id=message_id,
                    embedding=embedding_vector,
                    model=payload.get('model', EMBEDDING_MODEL)
                )
                logger.info(f"📝 Updated embedding for message {message_id}")
            else:
                # Create new embedding using the create_or_update method
                uow.embeddings.create_or_update(
                    message_id=message_id,
                    embedding=embedding_vector,
                    model=payload.get('model', EMBEDDING_MODEL)
                )
                logger.info(f"✨ Created new embedding for message {message_id}")
            
            # Mark job as completed
            uow.jobs.mark_completed(job_id)
            logger.info(f"✅ Job {job_id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}")
            
            # Mark job as failed (will retry if attempts < max_retries)
            uow.jobs.mark_failed(job_id, retry_delay_minutes=5)
            return False
    
    def _validate_job_payload(self, payload: dict) -> bool:
        """Validate that job payload has required fields."""
        required_fields = ['message_id', 'content']
        return all(field in payload for field in required_fields)
    
    def _log_stats(self):
        """Log current worker statistics."""
        runtime = datetime.utcnow() - self.stats['start_time']
        
        logger.info(f"📊 Worker {self.worker_id} stats:")
        logger.info(f"   Runtime: {runtime}")
        logger.info(f"   Jobs processed: {self.stats['jobs_processed']}")
        logger.info(f"   Successful: {self.stats['jobs_successful']}")
        logger.info(f"   Failed: {self.stats['jobs_failed']}")
        
        if self.stats['jobs_processed'] > 0:
            success_rate = (self.stats['jobs_successful'] / self.stats['jobs_processed']) * 100
            logger.info(f"   Success rate: {success_rate:.1f}%")
        
    def _log_final_stats(self):
        """Log final statistics when worker stops."""
        logger.info(f"🏁 Final stats for worker {self.worker_id}:")
        self._log_stats()


class EmbeddingWorkerManager:
    """Manages multiple embedding workers for concurrent processing."""
    
    def __init__(self, num_workers: int = 2):
        self.num_workers = num_workers
        self.workers = []
        self.threads = []
        
    def start(self):
        """Start all workers in separate threads."""
        logger.info(f"🚀 Starting {self.num_workers} embedding workers")
        
        for i in range(self.num_workers):
            worker = EmbeddingWorker(worker_id=f"worker-{i+1}")
            thread = threading.Thread(target=worker.start, name=f"EmbeddingWorker-{i+1}")
            
            self.workers.append(worker)
            self.threads.append(thread)
            thread.start()
            
        # Wait for all threads
        try:
            for thread in self.threads:
                thread.join()
        except KeyboardInterrupt:
            logger.info("Manager interrupted, stopping all workers")
            self.stop()
            
    def stop(self):
        """Stop all workers gracefully."""
        logger.info("🛑 Stopping all workers")
        for worker in self.workers:
            worker.stop()
        
        for thread in self.threads:
            thread.join(timeout=5)


@contextmanager
def embedding_worker_context(worker_id: str = None):
    """Context manager for running a single embedding worker."""
    worker = EmbeddingWorker(worker_id=worker_id)
    try:
        yield worker
    finally:
        worker.stop()


# CLI interface
def main():
    """Main entry point for running embedding workers."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Embedding Generation Worker")
    parser.add_argument("--workers", "-w", type=int, default=1, help="Number of worker threads")
    parser.add_argument("--worker-id", help="Specific worker ID (for single worker)")
    parser.add_argument("--batch-size", type=int, default=5, help="Max jobs per batch")
    parser.add_argument("--poll-interval", type=int, default=2, help="Poll interval in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(worker_id)s] %(message)s' if args.worker_id else 
               '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        if args.workers > 1:
            # Multi-worker mode
            manager = EmbeddingWorkerManager(num_workers=args.workers)
            manager.start()
        else:
            # Single worker mode
            worker = EmbeddingWorker(
                worker_id=args.worker_id,
                max_jobs_per_batch=args.batch_size,
                poll_interval_seconds=args.poll_interval
            )
            worker.start()
            
    except KeyboardInterrupt:
        logger.info("👋 Worker shutdown complete")
    except Exception as e:
        logger.error(f"❌ Worker failed: {e}")
        raise


if __name__ == "__main__":
    main()