# Python API

This library is in a very early stage and doesn't have a lot of features

## Quick Start

Use the CLI to set an account. Look at readme to see how.
```python
from claude_cli import Client

# Initialize the client
client = Client("account_name")  # The name you used when using claude add-account

# Create a conversation
conversation = client.create_conversation()

# Send a message and get a response
response = conversation.send_message("hi")
print(response.text)

# Delete the conversation
conversation.delete()
```

---

## Client Methods

### `client.create_conversation(name="")`

Create a new conversation.

**Parameters:**
- `name` (str, optional): Name for the conversation. Default is empty string.

**Returns:** `Conversation` object

---

### `client.get_conversation(conversation_id)`

Get an existing conversation by UUID.

**Parameters:**
- `conversation_id` (str): UUID of the conversation

**Returns:** `Conversation` object

---

### `client.list_conversations(limit=200, starred=False)`

List all conversations for the account.

**Parameters:**
- `limit` (int, optional): Maximum number of conversations to fetch. Default is 200.
- `starred` (bool, optional): If True, only return starred conversations. Default is False.

**Returns:** List of conversation dicts with keys: `uuid`, `name`, `created_at`, etc.

**Example:**
```python
conversations = client.list_conversations(limit=50)
for conv in conversations:
    print(f"{conv['name']} - {conv['uuid']}")
```

Note: If you want to get all conversations you gotta use the function twice with starred=False and starred=True. Just how claude works lol.

---

## Conversation Methods

### `conversation.send_message(prompt, stream=False)`

Send a message to the conversation.

**Parameters:**
- `prompt` (str): The message to send to Claude
- `stream` (bool, optional): If True, returns generator yielding text chunks. Default is False.

**Returns:** `Response` object (or generator if streaming)

**Example:**
```python
# Normal
response = conversation.send_message("hi")
print(response.text)

# Streaming
for chunk in conversation.send_message("whats 1 + 1", stream=True):
    print(chunk, end="", flush=True)
```

---

### `conversation.history(limit=None)`

Get message history for this conversation.

**Parameters:**
- `limit` (int, optional): Max messages to return (most recent). If None, returns all.

**Returns:** List of message dicts with keys: `sender`, `text`, `uuid`, `created_at`, `index`

**Example:**
```python
history = conversation.history(limit=10)
for msg in history:
    print(f"{msg['sender']}: {msg['text']}")
```

---

### `conversation.update_settings(settings)`

Update conversation settings.

**Parameters:**
- `settings` (dict): Settings to update

**Available settings:**
- `enabled_web_search` (bool): Enable web search
- `preview_feature_uses_artifacts` (bool): Enable artifacts
- `paprika_mode` (string): Enable extended thinking mode
- `enabled_turmeric` (bool): Enable computer use

**Example:**
```python
conversation.update_settings({
    "enabled_web_search": True,
    "preview_feature_uses_artifacts": True,
    "paprika_mode": "extended"
})
```

---

### `conversation.delete()`

Delete this conversation.

---

### `conversation.uuid`

The conversation's UUID (string).

---

## Response Object

Returned when sending messages (non-streaming mode).

**Attributes:**
- `text` (str): Main text response from Claude
- `artifacts` (list): Artifacts created (HTML, React, etc.)
- `files` (list): Files created by Claude
- `tool_uses` (list): Other tool uses (bash, file ops, etc.)

**Example:**
```python
response = conversation.send_message("Create a Python script")

# Text
print(response.text)

# Files
for file in response.files:
    print(f"Created: {file['path']}")
    with open(file['path'], 'w') as f:
        f.write(file['content'])

# Artifacts
for artifact in response.artifacts:
    print(f"{artifact['title']} - {artifact['language']}")

# Auto converts to string
print(response)  # Same as print(response.text)
```

**Artifact structure:**
```python
{
    'title': 'Component Name',
    'content': '...',
    'language': 'javascript',
    'type': 'application/vnd.ant.react',
    'command': 'create'
}
```

**File structure:**
```python
{
    'path': '/path/to/file.py',
    'content': '...',
    'description': 'Description...'
}
```

**Tool use structure:**
```python
{
    'name': 'bash_tool',
    'input': {...}
}
```