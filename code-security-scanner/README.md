# Code Security Scanner

![hero](public/hero.png)

A Next.js application that leverages Claude's AI capabilities to perform instant security vulnerability analysis on code snippets across multiple programming languages.

## Features

- **Multi-Language Support**: Analyze code in Python, JavaScript, TypeScript, C++, Java, Go, Rust, PHP, Ruby, C#, and more
- **AI-Powered Analysis**: Uses Claude (claude-sonnet-4-20250514) for deep security vulnerability detection
- **Structured Reports**: Returns detailed vulnerability reports with:
  - Vulnerability name and classification
  - Severity level (Critical / High / Medium / Low)
  - Line number identification
  - Clear descriptions of each issue
  - Actionable fix recommendations
- **Professional UI**: Clean, dark-themed interface with color-coded severity badges, animated loading states, and responsive layout

## Getting Started

### Prerequisites

- Node.js 18+ installed
- Anthropic API key ([get one here](https://console.anthropic.com/))

### Installation

1. Clone the repository:
```bash
git clone https://github.com/anthropics/anthropic-quickstarts.git
cd anthropic-quickstarts/code-security-scanner
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env.local` file in the root directory:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

4. Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Technology Stack

- **Frontend**:
  - Next.js 14
  - React
  - TailwindCSS
  - TypeScript
  - Lucide React (Icons)

- **Backend**:
  - Next.js API Routes
  - Edge Runtime
  - Anthropic SDK

## Usage Examples

Paste vulnerable code into the editor and click "Scan for Vulnerabilities" to get a detailed report.

### Example: Detecting Command Injection

```python
import os
user_input = input("Enter filename: ")
os.system(f"cat {user_input}")
```

### Example: Detecting SQL Injection

```python
import sqlite3
def get_user(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name = '{username}'")
    return cursor.fetchone()
```

## How It Works

This application uses the `@anthropic-ai/sdk` with Next.js API routes (Edge runtime). When you submit a code snippet, it sends a structured prompt to `claude-sonnet-4-20250514`. 

The system prompt explicitly instructs Claude to act as an expert code security auditor and return **only** a valid JSON object matching a strict schema for vulnerabilities, which includes the vulnerability name, a severity rating (Critical, High, Medium, Low), the specific line number, a description of the threat, and a recommended fix. The backend parses this JSON and returns it to the React frontend for rendering the interactive severity badges and report cards.

## Contributing

We welcome contributions to improve the Code Security Scanner! If you have ideas for enhancements or spot a bug, please open an issue or submit a pull request in the main [anthropic-quickstarts](https://github.com/anthropics/anthropic-quickstarts) repository.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
