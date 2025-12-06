from .base import Tool
import asyncio
import os
from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class BashTool(Tool):
    name: str = "bash"
    description: str = field(default="", init=False)
    input_schema: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "command": {
                "type": "string", 
                "description": "The bash command to execute"
            },
            "working_directory": {
                "type": "string",
                "description": "Working directory for command execution (optional, defaults to current directory)"
            }
        },
        "required": ["command"]
    }, init=False)
    
    # Permission settings
    allowed_commands: List[str] = field(default=None)
    denied_commands: List[str] = field(default_factory=list)
    working_directories: List[str] = field(default=None)
    allow_pipes: bool = field(default=True)
    allow_redirects: bool = field(default=True)
    timeout: int = field(default=30)

    def __post_init__(self): 
        # Build dynamic description based on permissions
        self.description = self._build_description()

    def _build_description(self) -> str:
        desc = "Execute bash commands in the system shell."
        
        # Add permission details
        if self.allowed_commands:
            desc += f"\n\nYou can ONLY use these commands: {', '.join(self.allowed_commands)}"
            desc += "\nExamples:"
            if 'git' in self.allowed_commands:
                desc += "\n- git status, git log, git diff"
            if 'npm' in self.allowed_commands:
                desc += "\n- npm install, npm run build, npm test"
            if 'ls' in self.allowed_commands:
                desc += "\n- ls -la, ls src/"
        else:
            desc += "\n\nYou can use any bash command except those explicitly denied."
        
        if self.denied_commands:
            desc += f"\n\nNEVER use these commands: {', '.join(self.denied_commands)}"
        
        if self.working_directories:
            desc += f"\n\nYou can only work in these directories: {', '.join(self.working_directories)}"
        
        # Feature restrictions
        features = []
        if not self.allow_pipes:
            features.append("pipes (|)")
        if not self.allow_redirects:
            features.append("redirects (>, <, >>)")
        
        if features:
            desc += f"\n\nThe following features are DISABLED: {', '.join(features)}"
        
        desc += f"\n\nCommands will timeout after {self.timeout} seconds."
        desc += "\n\nOutput includes stdout, stderr, and exit codes. Long outputs may be truncated."
        
        return desc

    async def execute(self, command: str, working_directory: Optional[str] = None) -> str:
        # Basic permission checks
        if not self._is_command_allowed(command):
            return "Error: Command not permitted by current permissions"
        
        if working_directory and not self._is_directory_allowed(working_directory):
            return f"Error: Working directory '{working_directory}' not permitted"
        
        if not self.allow_pipes and '|' in command:
            return "Error: Pipe operators not permitted"
        
        if not self.allow_redirects and any(op in command for op in ['>', '<', '>>']):
            return "Error: Redirect operators not permitted"
        
        # Execute command
        cwd = working_directory or os.getcwd()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return f"Error: Command timed out after {self.timeout} seconds"
            
            # Format output
            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += stderr.decode('utf-8', errors='replace')
            
            if process.returncode != 0:
                output += f"\n[Exit code: {process.returncode}]"
            
            return output.strip() or "[No output]"
            
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def _is_command_allowed(self, command: str) -> bool:
        # Get the base command (first word)
        base_command = command.split()[0] if command else ""
        
        # Check denied list first
        for denied in self.denied_commands:
            if base_command.startswith(denied):
                return False
        
        # If allowed list exists, command must be in it
        if self.allowed_commands:
            return any(base_command.startswith(allowed) for allowed in self.allowed_commands)
        
        # No allowed list means all non-denied commands are permitted
        return True
    
    def _is_directory_allowed(self, directory: str) -> bool:
        if not self.working_directories:
            return True
        
        # Normalize paths for comparison
        abs_dir = os.path.abspath(directory)
        return any(abs_dir.startswith(os.path.abspath(allowed)) 
                  for allowed in self.working_directories)