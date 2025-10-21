"""
Repository for job queue operations using PostgreSQL as the queue backend.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import desc, func, text, and_
from sqlalchemy.orm import Session

from db.models.models import Job
from db.repositories.base_repository import BaseRepository


class JobRepository(BaseRepository[Job]):
    """Repository for job queue operations."""
    
    def __init__(self, session: Session):
        super().__init__(session, Job)
    
    def enqueue(self, kind: str, payload: Dict[str, Any], 
               not_before: Optional[datetime] = None) -> Job:
        """Enqueue a new job."""
        from datetime import timezone
        job = Job(
            kind=kind,
            payload=payload,
            not_before=not_before or datetime.now(timezone.utc)
        )
        self.session.add(job)
        self.session.flush()
        return job
    
    def dequeue_next(self, kinds: Optional[List[str]] = None, 
                    max_attempts: int = 3) -> Optional[Job]:
        """
        Dequeue the next available job using FOR UPDATE SKIP LOCKED for concurrency.
        Returns None if no job is available.
        """
        # Build the query to find next available job
        if kinds:
            query = text("""
                UPDATE jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM jobs
                    WHERE status = 'pending'
                    AND not_before <= NOW()
                    AND attempts < :max_attempts
                    AND kind = ANY(:kinds)
                    ORDER BY not_before ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            """)
        else:
            query = text("""
                UPDATE jobs
                SET status = 'running',
                    attempts = attempts + 1,
                    updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM jobs
                    WHERE status = 'pending'
                    AND not_before <= NOW()
                    AND attempts < :max_attempts
                    ORDER BY not_before ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            """)
        
        if kinds:
            params = {
                'max_attempts': max_attempts,
                'kinds': kinds
            }
        else:
            params = {
                'max_attempts': max_attempts
            }
        
        result = self.session.execute(query, params)
        row = result.first()
        
        if row:
            # Convert the result row to a Job object
            job = Job(
                id=row.id,
                kind=row.kind,
                payload=row.payload,
                status=row.status,
                attempts=row.attempts,
                not_before=row.not_before,
                created_at=row.created_at,
                updated_at=row.updated_at
            )
            return job
        
        return None
    
    def mark_completed(self, job_id: int) -> bool:
        """Mark a job as completed."""
        job = self.session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'completed'
            job.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False
    
    def mark_failed(self, job_id: int, retry_delay_minutes: int = 5) -> bool:
        """Mark a job as failed and optionally schedule retry."""
        job = self.session.query(Job).filter(Job.id == job_id).first()
        if job:
            if job.attempts >= 3:  # Max attempts reached
                job.status = 'failed'
            else:
                # Schedule retry with exponential backoff
                delay_minutes = retry_delay_minutes * (2 ** (job.attempts - 1))
                job.status = 'pending'
                job.not_before = datetime.utcnow() + timedelta(minutes=delay_minutes)
            
            job.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False
    
    def requeue_job(self, job_id: int, not_before: Optional[datetime] = None) -> bool:
        """Requeue a job (reset to pending status)."""
        job = self.session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = 'pending'
            job.not_before = not_before or datetime.utcnow()
            job.updated_at = datetime.utcnow()
            self.session.flush()
            return True
        return False
    
    def get_pending_jobs(self, kinds: Optional[List[str]] = None, 
                        limit: int = 100) -> List[Job]:
        """Get pending jobs, optionally filtered by kind."""
        query = self.session.query(Job)\
            .filter(Job.status == 'pending')
        
        if kinds:
            query = query.filter(Job.kind.in_(kinds))
        
        return query.order_by(Job.not_before, Job.id)\
            .limit(limit)\
            .all()
    
    def get_running_jobs(self, limit: int = 100) -> List[Job]:
        """Get currently running jobs."""
        return self.session.query(Job)\
            .filter(Job.status == 'running')\
            .order_by(desc(Job.updated_at))\
            .limit(limit)\
            .all()
    
    def get_failed_jobs(self, limit: int = 100) -> List[Job]:
        """Get failed jobs."""
        return self.session.query(Job)\
            .filter(Job.status == 'failed')\
            .order_by(desc(Job.updated_at))\
            .limit(limit)\
            .all()
    
    def cleanup_old_completed_jobs(self, days_old: int = 7) -> int:
        """Clean up old completed jobs. Returns count of deleted jobs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        count = self.session.query(Job)\
            .filter(and_(
                Job.status == 'completed',
                Job.updated_at < cutoff_date
            ))\
            .count()
        
        self.session.query(Job)\
            .filter(and_(
                Job.status == 'completed',
                Job.updated_at < cutoff_date
            ))\
            .delete()
        
        self.session.flush()
        return count
    
    def cleanup_stuck_jobs(self, hours_stuck: int = 2) -> int:
        """
        Clean up jobs stuck in 'running' status for too long.
        Resets them to 'pending'. Returns count of jobs reset.
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_stuck)
        
        stuck_jobs = self.session.query(Job)\
            .filter(and_(
                Job.status == 'running',
                Job.updated_at < cutoff_time
            ))\
            .all()
        
        count = 0
        for job in stuck_jobs:
            job.status = 'pending'
            job.not_before = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            count += 1
        
        self.session.flush()
        return count
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics."""
        # Status counts
        status_counts = dict(
            self.session.query(Job.status, func.count(Job.id))
            .group_by(Job.status)
            .all()
        )
        
        # Kind counts for pending jobs
        kind_counts = dict(
            self.session.query(Job.kind, func.count(Job.id))
            .filter(Job.status == 'pending')
            .group_by(Job.kind)
            .all()
        )
        
        # Recent activity (last hour)
        recent_cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_jobs = self.session.query(func.count(Job.id))\
            .filter(Job.created_at >= recent_cutoff)\
            .scalar() or 0
        
        # Average processing time for completed jobs (last 100)
        avg_processing_query = text("""
            SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds
            FROM (
                SELECT updated_at, created_at
                FROM jobs
                WHERE status = 'completed'
                ORDER BY updated_at DESC
                LIMIT 100
            ) recent_jobs
        """)
        result = self.session.execute(avg_processing_query).first()
        avg_processing_seconds = float(result.avg_seconds) if result.avg_seconds else 0
        
        return {
            'status_counts': status_counts,
            'pending_by_kind': kind_counts,
            'recent_jobs_1h': recent_jobs,
            'avg_processing_seconds': round(avg_processing_seconds, 2),
            'total_jobs': sum(status_counts.values())
        }
    
    def get_embedding_job_stats(self) -> Dict[str, Any]:
        """Get statistics specifically for embedding generation jobs."""
        embedding_stats = self.session.query(
            Job.status,
            func.count(Job.id)
        ).filter(Job.kind == 'generate_embedding')\
        .group_by(Job.status)\
        .all()
        
        status_counts = dict(embedding_stats)
        
        # Recent embedding jobs (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_embedding_jobs = self.session.query(func.count(Job.id))\
            .filter(and_(
                Job.kind == 'generate_embedding',
                Job.created_at >= recent_cutoff
            ))\
            .scalar() or 0
        
        return {
            'embedding_jobs_by_status': status_counts,
            'recent_embedding_jobs_24h': recent_embedding_jobs,
            'total_embedding_jobs': sum(status_counts.values())
        }