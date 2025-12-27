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
        }
        mime_type = fallback_types.get(ext, 'text/plain')
    
    return mime_type

def find_file_references(prompt):
    """Find all @filename references in prompt"""
    pattern = r'@([^\s]+)'
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

def process_prompt_with_files(prompt):
    """Process prompt to extract @file references and create attachments"""
    file_refs = find_file_references(prompt)
    
    if not file_refs:
        return {
            'prompt': prompt,
            'attachments': [],
        }
    
    attachments = []
    files_found = []
    files_not_found = []
    
    for match_text, file_path in file_refs:
        resolved_path = resolve_file_path(file_path)
        
        if resolved_path:
            content = read_file_content(resolved_path)
            
            if content is not None:
                file_size = os.path.getsize(resolved_path)
                mime_type = get_mime_type(resolved_path)
                
                attachment = {
                    "file_name": file_path,
                    "file_type": mime_type,
                    "file_size": file_size,
                    "extracted_content": content,
                    "origin": "user_upload",
                    "kind": "file"
                }
                
                attachments.append(attachment)
                files_found.append(file_path)
            else:
                files_not_found.append(file_path)
        else:
            files_not_found.append(file_path)
    
    if files_not_found:
        raise FileNotFoundError(f"File(s) not found: {', '.join(files_not_found)}")
    
    return {
        'prompt': prompt,
        'attachments': attachments,
    }