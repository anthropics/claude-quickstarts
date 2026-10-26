# Manual Testing Guide for Advanced TIS

Since Puppeteer has Chromium launch issues on this macOS system, use this manual testing guide.

## Setup

1. Open `advanced.html` in your browser (double-click or `open advanced.html`)
2. Open browser DevTools (F12 or Cmd+Option+I)

## Test Checklist

### ✅ Agent Profile Selection
- [ ] Select "Intermediate Researcher" from agent dropdown
- [ ] Verify agent info card displays with name, stage, and achievements
- [ ] Check that neural parameters are loaded (visible in DevTools console)

### ✅ View Mode Toggle
- [ ] Click "Developer View" button
- [ ] Verify extended thinking, neural bank, and evolution log sections appear
- [ ] Click "Learner View" button
- [ ] Verify those sections hide

### ✅ Extended Thinking (Developer View)
- [ ] Enable Developer View
- [ ] Click "Run Self-Test" button
- [ ] Verify "🧠 Extended Thinking Process" section shows 6 steps:
  - Question Analysis
  - Key Concepts
  - Template Selection
  - Option 1-4 Evaluation
  - Strategy Integration
  - Final Decision

### ✅ Curriculum Learning
- [ ] Note current "Current Complexity" metric (starts at 1)
- [ ] Answer questions correctly to increase accuracy
- [ ] Watch for unlock messages: "🎓 Unlocked Complexity Level 2!"
- [ ] Verify complexity gates appear when accuracy is too low

### ✅ localStorage Persistence
- [ ] Answer several questions
- [ ] Note current cycle count and accuracy
- [ ] Click "💾 Save Progress" button
- [ ] Verify "✓ Progress auto-saved to localStorage" message appears
- [ ] Refresh the page
- [ ] Click "📂 Load Progress" button
- [ ] Verify metrics restore to previous values

### ✅ Background Mode
- [ ] Toggle "Background Mode" switch ON
- [ ] Click "Start Evolution"
- [ ] Verify questions don't display (silent operation)
- [ ] Verify metrics still update (cycles, accuracy)
- [ ] Toggle Background Mode OFF
- [ ] Verify questions now display normally

### ✅ Immediate Reinforcement Learning
- [ ] In Developer View, note strategy weights in Evolution Log
- [ ] Answer a question correctly
- [ ] Check console for weight updates
- [ ] Note neural pattern bank grows with successful patterns

### ✅ Meta-Learning Evolution
- [ ] Let system run for 8+ cycles
- [ ] Check Evolution Log for "🧬 Neural evolution" entries
- [ ] Verify exploration factor and weights change over time

## Expected Console Output Examples

```
[TIS] Agent Profile Loaded: Intermediate Researcher - Year 3-4 Graduate Studies
[TIS] Background mode: ON
[TIS] 🧬 Neural evolution: Accuracy 75.0%, Exploration 0.225
[TIS] 🎓 Unlocked Complexity Level 2 (Intermediate)!
✓ Loaded progress from 12/3/2025, 8:00:00 PM
```

## Success Criteria

✅ All features work without errors
✅ localStorage persists and restores correctly  
✅ Extended thinking shows detailed reasoning steps
✅ Curriculum gates higher complexity appropriately
✅ View modes show/hide content correctly
✅ Background mode suppresses UI but updates metrics

## Known Issues

- Puppeteer automated tests fail due to Chromium launch on macOS (arm64/Rosetta compatibility)
- Manual testing is required for verification
