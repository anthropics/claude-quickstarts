#!/usr/bin/env node

/**
 * Integration Test for Watson Glaser TIS
 * Validates file structure, dependencies, and data integrity
 */

const fs = require('fs');
const path = require('path');

const baseDir = path.join(__dirname, '..');
let passCount = 0;
let failCount = 0;

function test(name, fn) {
    try {
        const result = fn();
        if (result === true) {
            console.log(`✓ ${name}`);
            passCount++;
            return true;
        } else {
            console.log(`✗ ${name}: ${result}`);
            failCount++;
            return false;
        }
    } catch (e) {
        console.log(`✗ ${name}: ${e.message}`);
        failCount++;
        return false;
    }
}

function fileExists(filepath) {
    return fs.existsSync(path.join(baseDir, filepath));
}

function fileContains(filepath, text) {
    const content = fs.readFileSync(path.join(baseDir, filepath), 'utf8');
    return content.includes(text);
}

console.log('\n🧪 Watson Glaser TIS Integration Tests\n');
console.log('='.repeat(50) + '\n');

// File Structure Tests
console.log('📁 File Structure:');
test('advanced.html exists', () => fileExists('advanced.html'));
test('agent_profiles.js exists', () => fileExists('agent_profiles.js'));
test('iframe_wrapper.html exists', () => fileExists('iframe_wrapper.html'));
test('design_tokens.json exists', () => fileExists('design/design_tokens.json'));
test('README.md exists', () => fileExists('README.md'));

// Content Validation Tests
console.log('\n📝 Content Validation:');
test('advanced.html loads agent_profiles.js', () => 
    fileContains('advanced.html', 'agent_profiles.js'));
test('advanced.html has agentSelector element', () => 
    fileContains('advanced.html', 'id="agentSelector"'));
test('advanced.html has cycleCount element', () => 
    fileContains('advanced.html', 'id="cycleCount"'));
test('advanced.html has startBtn element', () => 
    fileContains('advanced.html', 'id="startBtn"'));
test('advanced.html has view mode toggle', () => 
    fileContains('advanced.html', 'data-mode="learner"'));
test('advanced.html has localStorage save', () => 
    fileContains('advanced.html', 'saveToLocalStorage'));
test('advanced.html has extended thinking', () => 
    fileContains('advanced.html', 'extendedThinking'));
test('advanced.html has curriculum learning', () => 
    fileContains('advanced.html', 'checkCurriculumGate'));

// Agent Profiles Tests
console.log('\n👥 Agent Profiles:');
const agentProfilesPath = path.join(baseDir, 'agent_profiles.js');
const agentContent = fs.readFileSync(agentProfilesPath, 'utf8');

test('agent_profiles.js exports AGENT_PROFILES', () => 
    agentContent.includes('window.AGENT_PROFILES'));

// Load and validate agent profiles
const AGENT_PROFILES = eval(`
    const window = {};
    ${agentContent}
    window.AGENT_PROFILES;
`);

test('10 agent profiles exist', () => AGENT_PROFILES.length === 10 || `Found ${AGENT_PROFILES.length}`);
test('All profiles have id', () => 
    AGENT_PROFILES.every(p => p.id) || 'Missing id on some profiles');
test('All profiles have name', () => 
    AGENT_PROFILES.every(p => p.name) || 'Missing name on some profiles');
test('All profiles have stage', () => 
    AGENT_PROFILES.every(p => p.stage) || 'Missing stage on some profiles');
test('All profiles have neuralParams', () => 
    AGENT_PROFILES.every(p => p.neuralParams) || 'Missing neuralParams on some profiles');
test('All profiles have achievements', () => 
    AGENT_PROFILES.every(p => Array.isArray(p.achievements)) || 'Missing achievements on some profiles');

const expectedIds = [
    'novice-student',
    'apprentice-analyst',
    'intermediate-researcher',
    'advanced-practitioner',
    'emerging-expert',
    'senior-researcher',
    'principal-investigator',
    'cognitive-architect',
    'ethics-policy-lead',
    'professor-emeritus'
];

test('All expected profile IDs present', () => {
    const ids = AGENT_PROFILES.map(p => p.id);
    const missing = expectedIds.filter(id => !ids.includes(id));
    return missing.length === 0 || `Missing: ${missing.join(', ')}`;
});

test('All profile IDs are unique', () => {
    const ids = AGENT_PROFILES.map(p => p.id);
    return ids.length === new Set(ids).size || 'Duplicate IDs found';
});

test('All IDs are kebab-case', () => 
    AGENT_PROFILES.every(p => /^[a-z]+(-[a-z]+)*$/.test(p.id)) || 'Non-kebab-case IDs found');

// Neural Parameters Tests
console.log('\n🧠 Neural Parameters:');
test('All profiles have logicalDepth', () => 
    AGENT_PROFILES.every(p => typeof p.neuralParams.logicalDepth === 'number'));
test('All profiles have abstractionLevel', () => 
    AGENT_PROFILES.every(p => typeof p.neuralParams.abstractionLevel === 'number'));
test('All profiles have creativityFactor', () => 
    AGENT_PROFILES.every(p => typeof p.neuralParams.creativityFactor === 'number'));
test('All profiles have patternRecognition', () => 
    AGENT_PROFILES.every(p => typeof p.neuralParams.patternRecognition === 'number'));

// Puppeteer Test Validation
console.log('\n🤖 Test Files:');
test('puppeteer_test.js exists', () => fileExists('tests/puppeteer_test.js'));
test('puppeteer_test.js uses correct selectors', () => {
    const testContent = fs.readFileSync(path.join(baseDir, 'tests/puppeteer_test.js'), 'utf8');
    return testContent.includes('#agentSelector') && 
           testContent.includes('cycleCount') &&
           testContent.includes('#startBtn');
});
test('puppeteer_test.js uses agent IDs', () => {
    const testContent = fs.readFileSync(path.join(baseDir, 'tests/puppeteer_test.js'), 'utf8');
    return testContent.includes('intermediate-researcher') || testContent.includes('emerging-expert');
});
test('validation.html exists', () => fileExists('tests/validation.html'));
test('manual_test.md exists', () => fileExists('tests/manual_test.md'));

// Design System Tests
console.log('\n🎨 Design System:');
const designTokens = JSON.parse(fs.readFileSync(path.join(baseDir, 'design/design_tokens.json'), 'utf8'));
test('design_tokens.json is valid JSON', () => true);
test('design_tokens has colors', () => designTokens.colors !== undefined);
test('design_tokens has typography', () => designTokens.typography !== undefined);
test('design_tokens has spacing', () => designTokens.spacing !== undefined);

// Summary
console.log('\n' + '='.repeat(50));
console.log(`\n📊 Test Results: ${passCount}/${passCount + failCount} passed\n`);

if (failCount === 0) {
    console.log('🎉 All tests passed! System is ready.\n');
    process.exit(0);
} else {
    console.log(`⚠️  ${failCount} test(s) failed. Please fix issues.\n`);
    process.exit(1);
}
