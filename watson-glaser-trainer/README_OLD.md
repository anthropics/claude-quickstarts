# Watson Glaser Critical Thinking Trainer

An interactive practice tool for the Watson Glaser Critical Thinking Appraisal, commonly used in legal and professional recruitment.

## What is the Watson Glaser Test?

The Watson Glaser Critical Thinking Appraisal measures five aspects of critical thinking:

1. **Assumptions** - Identifying unstated premises that must be true for a statement to hold
2. **Inferences** - Evaluating conclusions drawn from given information  
3. **Deductions** - Determining if conclusions follow necessarily from premises
4. **Interpretation** - Assessing whether conclusions follow beyond reasonable doubt
5. **Evaluation of Arguments** - Judging the strength and relevance of arguments

## Usage

Simply open `index.html` in any web browser. No server or installation required.

```bash
# On macOS
open index.html

# Or just double-click the file in Finder
```

## Current Features

- **Assumptions Section** - 5 practice questions with detailed explanations
- **Inferences Section** - 5 practice questions with detailed explanations
- Immediate feedback after each answer
- Score tracking within each section
- Clean, focused interface

## Planned Features

- [ ] Deductions section
- [ ] Interpretation section  
- [ ] Evaluation of Arguments section
- [ ] Timed test mode (simulating real Watson Glaser timing)
- [ ] Progress tracking across sessions (localStorage)
- [ ] More questions per section
- [ ] Difficulty progression
- [ ] Performance analytics by question type

## Project Structure

```
watson-glaser-trainer/
├── index.html       # Self-contained application
├── README.md        # This file
└── questions/       # (Future) Modular question banks
```

## Development Notes

The current implementation is a single HTML file with embedded CSS and JavaScript for maximum portability. As the project grows, it can be refactored into:

- Separate question bank JSON files
- Modular JavaScript components
- A proper build system (Vite/React) if needed

## License

MIT
