# Contributing to Watson Glaser Test Intelligence System

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🎯 Ways to Contribute

- **Bug Reports**: Report issues you encounter
- **Feature Requests**: Suggest new features or enhancements
- **Code Contributions**: Submit pull requests
- **Documentation**: Improve or expand documentation
- **Testing**: Help with test coverage
- **Design**: UI/UX improvements

## 🐛 Reporting Issues

When reporting an issue, please include:

1. **Description**: Clear description of the problem
2. **Steps to Reproduce**: Detailed steps to reproduce the issue
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: Browser, OS, version
6. **Screenshots**: If applicable
7. **Console Errors**: Any JavaScript errors

### Issue Template

```markdown
**Description**
[Clear description of the issue]

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

**Expected Behavior**
[What should happen]

**Actual Behavior**
[What actually happens]

**Environment**
- Browser: [e.g., Chrome 120]
- OS: [e.g., macOS 14.0]
- Version: [e.g., 1.0.0]

**Screenshots**
[If applicable]

**Console Errors**
[Paste any JavaScript errors]
```

## 💡 Feature Requests

When suggesting a feature:

1. **Use Case**: Describe the problem it solves
2. **Proposed Solution**: How you envision it working
3. **Alternatives**: Other solutions you've considered
4. **Impact**: Who benefits and how

## 🔧 Development Setup

1. **Fork the Repository**

   ```bash
   # Click "Fork" on GitHub
   git clone https://github.com/YOUR_USERNAME/claude-quickstarts.git
   cd claude-quickstarts/watson-glaser-trainer
   ```

2. **Create a Branch**

   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Make Changes**
   - Edit the relevant files
   - Follow the coding standards below
   - Test your changes thoroughly

4. **Test Your Changes**

   ```bash
   # Run automated tests
   npm install
   npm run test-puppeteer
   
   # Manual testing
   open advanced.html
   open tests/validation.html
   ```

5. **Commit Your Changes**

   ```bash
   git add .
   git commit -m "feat: add your feature description"
   # or
   git commit -m "fix: fix your bug description"
   ```

6. **Push to Your Fork**

   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template

## 📝 Coding Standards

### JavaScript

- **ES6+**: Use modern JavaScript features
- **No Dependencies**: Keep it vanilla JavaScript
- **Comments**: Document complex logic
- **Naming**: Use descriptive variable names
- **Formatting**: 4-space indentation, consistent style

```javascript
// Good
function calculateAccuracy(correct, total) {
    if (total === 0) return 0;
    return (correct / total) * 100;
}

// Bad
function calc(c,t){if(t==0)return 0;return c/t*100;}
```

### HTML

- **Semantic**: Use semantic HTML5 elements
- **Accessibility**: Include ARIA labels where needed
- **Indentation**: 4 spaces
- **Comments**: Document sections

### CSS

- **Classes**: Use descriptive class names
- **Organization**: Group related styles
- **Comments**: Document complex styles
- **Units**: Use rem/em for responsive design

## 🧪 Testing Requirements

All contributions should include tests:

### For Bug Fixes

- Add a test that reproduces the bug
- Verify the test fails without your fix
- Verify the test passes with your fix

### For New Features

- Add unit tests for new functions
- Add integration tests for new workflows
- Update manual test guide if needed

### Running Tests

```bash
# Automated tests
npm run test-puppeteer

# Manual validation
open tests/validation.html
follow tests/manual_test.md
```

## 📋 Pull Request Guidelines

### PR Title Format

Use conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting)
- `refactor:` Code refactoring
- `test:` Adding/updating tests
- `chore:` Maintenance tasks

Examples:

- `feat: add export functionality for neural banks`
- `fix: resolve localStorage quota exceeded error`
- `docs: update installation instructions`

### PR Description Template

```markdown
## Description
[Clear description of changes]

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Browser compatibility checked

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] All tests pass

## Screenshots
[If applicable]

## Related Issues
Closes #[issue number]
```

## 🔍 Code Review Process

1. **Automated Checks**: CI must pass
2. **Manual Review**: Maintainer reviews code
3. **Testing**: Verify changes work as expected
4. **Feedback**: Address review comments
5. **Approval**: Maintainer approves PR
6. **Merge**: PR is merged to main branch

## 📚 Documentation Standards

### Code Comments

```javascript
/**
 * Applies multi-strategy reasoning to answer a question
 * @param {Object} question - Question object with context and options
 * @returns {Object} Reasoning result with confidence and strategies
 */
function applyMultiStrategyReasoning(question) {
    // Implementation
}
```

### README Updates

When adding features:

- Update Features section
- Add usage examples
- Update screenshots if UI changed
- Add to troubleshooting if needed

### Inline Documentation

```javascript
// Neural parameter evolution - adjust based on performance
// Higher accuracy = slower exploration, more exploitation
if (accuracy > 0.7) {
    this.neuralParams.explorationFactor *= 0.9; // Reduce exploration
}
```

## 🎨 Design Guidelines

### UI/UX Principles

- **Simplicity**: Keep interfaces clean and intuitive
- **Consistency**: Maintain consistent design patterns
- **Accessibility**: Ensure WCAG 2.1 AA compliance
- **Responsiveness**: Support mobile and desktop
- **Performance**: Optimize for speed

### Color Palette

Follow `design/design_tokens.json`:

- Primary: #667eea (purple)
- Success: #48bb78 (green)
- Error: #f56565 (red)
- Warning: #f39c12 (orange)
- Info: #4299e1 (blue)

## 🚀 Release Process

1. **Version Bump**: Update version in relevant files
2. **Changelog**: Update with changes
3. **Testing**: Full regression test
4. **Documentation**: Update docs
5. **Tag**: Create git tag
6. **Release**: Create GitHub release

## 💬 Communication

- **Issues**: Use GitHub Issues for bugs/features
- **Discussions**: Use GitHub Discussions for questions
- **Security**: Email <security@example.com> for security issues

## 📖 Resources

- [JavaScript Style Guide](https://github.com/airbnb/javascript)
- [HTML Best Practices](https://github.com/hail2u/html-best-practices)
- [CSS Guidelines](https://cssguidelin.es/)
- [Git Commit Messages](https://chris.beams.io/posts/git-commit/)

## 🙏 Recognition

Contributors will be:

- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation

## ❓ Questions

If you have questions:

1. Check existing documentation
2. Search closed issues
3. Open a new discussion
4. Contact maintainers

Thank you for contributing! 🎉
