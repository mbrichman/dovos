# Delete Conversation Feature

## Overview
Users can now delete conversations from the Flask UI, which will remove the conversation along with all associated messages and embeddings from the database.

## Implementation

### Database Layer
- **Cascade Deletion**: The PostgreSQL schema uses `ON DELETE CASCADE` foreign key constraints to automatically delete:
  - All messages in the conversation (`messages.conversation_id`)
  - All embeddings for those messages (`message_embeddings.message_id`)

### Repository Layer
- `ConversationRepository.delete_conversation_with_cascade()`: Deletes a conversation by UUID, leveraging PostgreSQL's cascade delete

### Controller Layer
- `PostgresController.delete_conversation()`: API endpoint handler that:
  - Validates UUID format
  - Calls repository delete method
  - Returns success/failure response

### Routes Layer
- `DELETE /api/conversation/<doc_id>`: REST endpoint for deleting conversations
  - Returns 200 on success with `{"success": true, "message": "..."}`
  - Returns 400 on failure with `{"success": false, "message": "..."}`

### UI Layer
- **Delete Button**: Added to conversation menu dropdown in conversations list
  - Red/danger styling to indicate destructive action
  - Confirmation dialog before deletion
  - Smooth fade-out animation on successful delete
  - Error notification if delete fails
  - Auto-reloads page if no conversations remain

## Usage

1. Navigate to the conversations list (`/conversations`)
2. Click the three-dot menu (⋯) on any conversation
3. Click "Delete" (red button with trash icon)
4. Confirm the deletion in the dialog
5. Conversation fades out and is removed from the database

## Safety Features

- **Confirmation Dialog**: Users must confirm before deletion
- **Clear Warning**: Dialog explains that deletion is permanent and includes messages & embeddings
- **Visual Feedback**: Red/danger styling makes it clear this is a destructive action
- **Proper Error Handling**: If deletion fails, the UI shows an error message and doesn't remove the item

## Technical Notes

- Deletion is atomic (single transaction)
- No orphaned data due to cascade constraints
- Compatible with PostgreSQL backend only (legacy mode returns 501)
- UUID validation prevents injection attacks
