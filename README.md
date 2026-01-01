# unoffical claude-cli 0.6.0

![Claude CLI REPL](src/cli/repl_showcase.png)

---

### Install

No offical package yet\
Python 3.10+

```bash
# Clone the repository
git clone https://github.com/TheTank10/claude-cli
cd claude-cli

# Install with pip
pip install -e .

# Verify installation
claude test
```
---

### Usage

#### Account Management

**Add your first account:**
```bash
claude add-account
```
You'll be prompted for:
- Account name (anything you want)
- Claude cookies (paste from browser)

**List all accounts:**
```bash
claude accounts
```
Shows all saved accounts with `->` indicating the active one.

**Switch between accounts:**
```bash
claude switch-account
```

**Update expired cookies:**
```bash
claude update-account
```

**Remove an account:**
```bash
claude remove-account
```

#### Getting Your Cookies

1. Log into [claude.ai](https://claude.ai) in your browser
2. Open Developer Tools (F12)
3. Click on network
4. Refresh the page and click on a fetch request such as "count_all"
5. Check the request headers and copy `Cookies`

#### Chatting with Claude

**List conversations:**
```bash
claude conversations
```
Allows you to switch to previous conversations you've had with claude.

**Create new conversation:**
```bash
claude new # Claude chooses a name for this conversation
claude new --name "My Project" 
```

**Send a message:**
```bash
claude chat prompt # Streams to output with markdown using the rich library
claude chat "prompt" --raw # Streams to output without markdown 
claude chat "prompt" > response.md # Streams response to a file

# Sending attachments/files
claude chat "explain @main.py" 
claude chat "explain @src/cli/chat.py and @src/__init__.py"
claude chat "explain @c:\Users\User\OneDrive\Desktop\code\claude-cli\src\cli\chat.py"
```

** REPL mode:**

```bash
# Works just like claude chat except its interactive
claude repl
claude repl --raw
```

Note: To make uploading files easier add @ then drag and drop the file into your terminal.\
Most terminals will support this.

**Configure settings:**
```bash
claude settings
```
Toggle web search, extended thinking, and artifacts.

**Rename conversation:**
```bash
claude name # Shows the name of the conversation
claude name New Name
```

**Sync conversation:**
```bash
claude sync
```
Updates local state with latest messages from web.\
⚠️ Important: If you talk to claude on your browser and come back later to the cli and don't sync the conversations it will remove the history up to the last chat claude sent through the cli

**Delete current conversation:**
```bash
claude delete
```

**Get chat history:**
```bash
claude history # Last 30 messages with rich markdowns
claude history 5 # Last x messages 
claude history --raw # No rich markdowns
claude history > output.md # Redirect to file
```

**Search current conversation:**
```bash
claude search query # Shows interactively
claude search "query" > results.txt # Redirects all results to a file
claude search "query" -o folder # Creates a folder with text files representing results
```

Currently this tool only searches for text found in: text, files, coding artifacts\
should probably make it search more things later on

**Export conversation/s:**
```bash
claude export # Interactive
claude export this/all/choose js/md directory_name # Dont enter dir name with 'this'
```

```claude --help``` for a list of commands

---

## TODO

### High Priority
- [x] Add conversation history viewer
- [x] Support file uploads (Some file types might not work. Some need to be passed through the convert_document endpoint which is not yet implemented.)
- [x] Add conversation search/filter
- [x] Export conversations to markdown/json
- [ ] Python API that mimicks offical API (wont release until done)
- [x] REPL mode

### Mid Priority
- [ ] Styles
- [ ] Automatic session gathering maybe with a web driver?
- [ ] Clearing chat history 
- [ ] Incognito mode
- [ ] Batch operations (clear all, delete all)

### Low priorty
- [ ] claude retry
- [ ] Show when claude is thinking/seraching/coding
- [ ] Prompt input redirection

---

This tool is completely unofficial and has no affilation to anthropic\
All contributions are welcome