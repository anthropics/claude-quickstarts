# Watson Glaser Test Intelligence System (TIS)

A self-evolving AI system for Watson-Glaser Critical Thinking training with Extended Thinking capabilities and neural evolution.

## 🧠 Overview

The Watson Glaser Test Intelligence System (TIS) is an advanced, self-contained critical thinking training platform that uses:

- **Extended Thinking Architecture**: Multi-layer reasoning with 4x, 8x, 16x, and 32x configurations
- **Logic Prioritization**: 75% weight to reasoning layers vs consensus voting
- **Neural Evolution**: Self-modifying parameters based on performance
- **Curriculum Learning**: Progressive difficulty gating based on accuracy
- **Meta-Learning**: Adaptive strategy weights and cognitive templates
- **LocalStorage Persistence**: Auto-save progress across sessions

## 🚀 Quick Start

### Prerequisites

- Modern web browser (Chrome, Firefox, Safari, Edge)
- Node.js 16+ (for running tests only)
- No API keys required - runs entirely client-side

### Running the Application

#### Option 1: Direct Browser Access

```bash
# From the watson-glaser-trainer directory
open advanced.html
```

#### Option 2: Local Server (Recommended)

```bash
# Using Python
cd watson-glaser-trainer
python3 -m http.server 8080

# Using Node.js
npx http-server . -p 8080

# Then open: http://localhost:8080/advanced.html
```

### Quick Test

```bash
# Install test dependencies
npm install

# Run automated tests
npm run test-puppeteer
```

## 📁 Project Structure

```
watson-glaser-trainer/
├── README.md                    # This file
├── LICENSE                      # MIT License
├── SECURITY.md                  # Security policy
├── CONTRIBUTING.md              # Contribution guidelines
├── advanced.html                # Main TIS application
├── four_layer.html              # Alternative 4-layer view
├── iframe_wrapper.html          # Embeddable wrapper
├── agent_profiles.js            # Pre-trained agent configurations
├── PROJECT_STATUS.md            # Implementation status
├── VERIFICATION_COMPLETE.md     # Testing verification
├── design/
│   └── design_tokens.json      # UI design system
└── tests/
    ├── puppeteer_test.js       # Automated browser tests
    ├── integration_test.js     # Integration test suite
    ├── manual_test.md          # Manual testing guide
    └── validation.html         # Validation interface
```

## 🎯 Features

### Core Capabilities

- **5 Question Types**: Assumptions, Inferences, Deductions, Interpretations, Evaluations
- **8 Agent Profiles**: From Novice Learner to Accomplished Expert
- **Extended Thinking**: Chain-of-thought reasoning with multi-step analysis
- **Background Mode**: Silent evolution for autonomous learning
- **Progress Persistence**: Auto-save to localStorage every 5 cycles

### Developer Features

- **Thinking Process Visualization**: See chain-of-thought reasoning
- **Neural Pattern Bank**: Inspect learned patterns
- **Evolution Log**: Monitor meta-learning progress
- **Strategy Weights**: View adaptive reasoning strategy weights
- **Cognitive Metrics**: Track 4 cognitive capability scores

## 🧪 Testing

```bash
# Install dependencies
npm install

# Run automated tests
npm run test-puppeteer

# Run manual validation
open tests/validation.html
```

## 📊 Architecture

### Extended Thinking Layers (8x Default)

```
Layer 1: Initial Perception      (perception)
Layer 2: Deductive Reasoning     (logic) ⚡ 75% weight
Layer 3: Pattern Recognition     (perception)
Layer 4: Inductive Reasoning     (logic) ⚡ 75% weight
Layer 5: Critical Evaluation     (evaluation)
Layer 6: Alternative Analysis    (evaluation)
Layer 7: Meta-Analysis          (meta)
Layer 8: Consensus Synthesis    (synthesis)
```

### Logic Prioritization

- **Logic Layers**: 75% voting weight
- **Other Layers**: 25% voting weight
- Ensures reasoning quality dominates consensus

## 🔒 Security & Privacy

- **No Server Required**: Runs entirely in browser
- **No Data Transmission**: All processing client-side
- **No API Keys**: No external services used
- **LocalStorage Only**: Data stays on user's device
- **No Tracking**: No analytics or telemetry

## 📜 License

MIT License - See [LICENSE](LICENSE)

Copyright (c) 2024 Christian Smith

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 🛡️ Security

For security concerns, see [SECURITY.md](SECURITY.md)

## 📚 Documentation

- [Extended Thinking Implementation](../EXTENDED_THINKING_IMPLEMENTATION.md)
- [8x Architecture Guide](../8X_ARCHITECTURE.md)
- [Scalability Analysis](../SCALABILITY_ANALYSIS.md)
- [Project Status](PROJECT_STATUS.md)

## 🐛 Troubleshooting

### Questions Not Generating

- Check browser console for errors
- Ensure JavaScript is enabled
- Try clearing localStorage: `localStorage.clear()`

### Evolution Not Starting

- Verify agent profile is selected
- Click Start Evolution button
- Check browser tab is active

### Progress Not Saving

- Check localStorage quota
- Try manual save button
- Check browser privacy settings

## 📞 Support

For questions or issues, open a GitHub issue or check the documentation.

---

**Version**: 1.0.0  
**Status**: Production Ready ✅
