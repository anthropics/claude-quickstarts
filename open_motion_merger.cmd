@echo off
echo Opening unified-redaction-hub in VS Code with WSL Remote...
code \\wsl.localhost\Ubuntu\home\lroc\unified-redaction-hub
echo.
echo VS Code should now be opening with the unified-redaction-hub project.
echo Once open, use the integrated terminal to activate the virtual environment:
echo   source venv/bin/activate 
echo.
echo You can then run the application using:echo   python app.py
echo.
echo Press any key to exit...
pause > nul
