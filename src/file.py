import os
import re
import mimetypes
from pathlib import Path

def get_mime_type(file_path):
    """Get MIME type for a file path"""
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type is None:
        ext = Path(file_path).suffix.lower()
        fallback_types = {
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
            '.jsx': 'text/jsx',
            '.tsx': 'text/tsx',
            '.json': 'application/json',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.css': 'text/css',
            '.xml': 'text/xml',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml',
            '.sh': 'text/x-shellscript',
            '.bat': 'text/x-batch',
            # Office documents
            # PDFs
            '.pdf': 'application/pdf',
            # Images
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        mime_type = fallback_types.get(ext, 'application/octet-stream')
    
    return mime_type

def needs_upload(mime_type):
    """Determine if a file needs to be uploaded vs sent as attachment"""
    # Files that can be sent as text attachments
    text_types = [
        'text/',  # All text/* types
        'application/json',
        'application/xml',
        'application/javascript',
        'application/x-yaml',
        'application/yaml',
        'application/sql',
        'application/x-python',
        'application/x-sh',
        'application/x-shellscript',
        'application/x-ruby',
        'application/x-perl',
        'application/x-php',
        'application/x-httpd-php',
        'application/typescript',
        'application/x-typescript',
    ]
    
    for text_type in text_types:
        if mime_type.startswith(text_type):
            return False
    
    return True

def find_file_references(prompt):
    """Find all @filename references in prompt"""
    pattern = r'(?<!\w)@([^\s]+)'
    matches = re.finditer(pattern, prompt)
    
    file_refs = []
    for match in matches:
        match_text = match.group(0)
        file_path = match.group(1)
        file_refs.append((match_text, file_path))
    
    return file_refs

def read_file_content(file_path):
    """Read file content as text, returns None on error"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return None

def resolve_file_path(file_path):
    """Resolve file path (absolute or relative to cwd)"""
    path = Path(file_path)
    
    if path.is_absolute():
        return str(path) if path.exists() else None
    
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return str(cwd_path)
    
    return None

def process_prompt_with_files(prompt, session, org_id):
    """Process prompt to extract @file references and create attachments/uploads"""
    from src.claude import upload_file
    
    file_refs = find_file_references(prompt)
    
    if not file_refs:
        return {
            'prompt': prompt,
            'attachments': [],
            'files': [],
        }
    
    attachments = []
    file_uuids = []
    files_not_found = []
    
    for match_text, file_path in file_refs:
        resolved_path = resolve_file_path(file_path)
        
        if not resolved_path:
            files_not_found.append(file_path)
            continue
        
        mime_type = get_mime_type(resolved_path)
        
        if needs_upload(mime_type):
            # Binary file - upload it via claude.py
            try:
                response = upload_file(session, org_id, resolved_path)
                response.raise_for_status()
                result = response.json()
                
                if not result.get('success'):
                    raise Exception(f"Upload failed for {file_path}")
                
                file_uuid = result['file_uuid']
                file_uuids.append(file_uuid)
            except Exception as e:
                raise Exception(f"Failed to upload {file_path}: {str(e)}")
        else:
            # Text file - can be sent as attachment
            content = read_file_content(resolved_path)
            
            if content is None:
                files_not_found.append(file_path)
                continue
            
            file_size = os.path.getsize(resolved_path)
            
            attachment = {
                "file_name": file_path,
                "file_type": mime_type,
                "file_size": file_size,
                "extracted_content": content,
                "origin": "user_upload",
                "kind": "file"
            }
            
            attachments.append(attachment)
    
    if files_not_found:
        raise FileNotFoundError(f"File(s) not found or unreadable: {', '.join(files_not_found)}")
    
    return {
        'prompt': prompt,
        'attachments': attachments,
        'files': file_uuids,
    }