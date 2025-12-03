// Agent profiles representing stages of learning and career milestones
// Exposed as `window.AGENT_PROFILES` for easy integration into the TIS UI

window.AGENT_PROFILES = [
  {
    name: 'Novice Student',
    stage: 'Year 1 - Curious Learner',
    neuralParams: {
      logicalDepth: 1.5,
      abstractionLevel: 0.45,
      creativityFactor: 0.4,
      ambiguityTolerance: 0.1,
      metaLearningRate: 0.05,
      reasoningComplexity: 1.2,
      cognitiveDiversity: 0.2,
      patternRecognition: 0.5,
      logicalConsistency: 0.6,
      adaptiveThreshold: 0.4
    },
    achievements: [
      { year: 'Year 1', title: 'Intro to Logic', description: 'Learned basic identification of premises and conclusions.' },
      { year: 'Year 1', title: 'Simple Assumptions', description: 'Practiced spotting obvious assumptions in short passages.' }
    ]
  },
  {
    name: 'Apprentice Analyst',
    stage: 'Year 2-3 - Structured Thinker',
    neuralParams: {
      logicalDepth: 2.2,
      abstractionLevel: 0.55,
      creativityFactor: 0.55,
      ambiguityTolerance: 0.12,
      metaLearningRate: 0.07,
      reasoningComplexity: 1.7,
      cognitiveDiversity: 0.35,
      patternRecognition: 0.6,
      logicalConsistency: 0.7,
      adaptiveThreshold: 0.5
    },
    achievements: [
      { year: 'Year 2', title: 'Statistical Reasoning', description: 'Understood majority vs. representativeness in inferences.' },
      { year: 'Year 3', title: 'Conditional Logic', description: 'Practiced truth conditions, necessary vs sufficient assumptions.' }
    ]
  },
  {
    name: 'Intermediate Researcher',
    stage: 'Year 4-5 - Analytical Practitioner',
    neuralParams: {
      logicalDepth: 3.0,
      abstractionLevel: 0.7,
      creativityFactor: 0.7,
      ambiguityTolerance: 0.18,
      metaLearningRate: 0.12,
      reasoningComplexity: 2.4,
      cognitiveDiversity: 0.5,
      patternRecognition: 0.75,
      logicalConsistency: 0.82,
      adaptiveThreshold: 0.65
    },
    achievements: [
      { year: 'Year 4', title: 'Controlled Experiments', description: 'Designed simple tests to disambiguate causation from correlation.' },
      { year: 'Year 5', title: 'Peer Review', description: 'Refined reasoning via feedback loops and critiques.' }
    ]
  },
  {
    name: 'Advanced Practitioner',
    stage: 'Year 6-7 - Skilled Reasoner',
    neuralParams: {
      logicalDepth: 3.8,
      abstractionLevel: 0.82,
      creativityFactor: 0.85,
      ambiguityTolerance: 0.22,
      metaLearningRate: 0.18,
      reasoningComplexity: 3.2,
      cognitiveDiversity: 0.68,
      patternRecognition: 0.88,
      logicalConsistency: 0.9,
      adaptiveThreshold: 0.78
    },
    achievements: [
      { year: 'Year 6', title: 'Complex Inference', description: 'Accurately synthesizes multiple probabilistic cues in inference tasks.' },
      { year: 'Year 7', title: 'Instructional Design', description: 'Authored training exercises to teach reasoning skills.' }
    ]
  },
  {
    name: 'Emerging Expert',
    stage: 'Year 8 - Domain Specialist',
    neuralParams: {
      logicalDepth: 4.5,
      abstractionLevel: 0.9,
      creativityFactor: 1.0,
      ambiguityTolerance: 0.28,
      metaLearningRate: 0.22,
      reasoningComplexity: 3.8,
      cognitiveDiversity: 0.78,
      patternRecognition: 0.95,
      logicalConsistency: 0.94,
      adaptiveThreshold: 0.85
    },
    achievements: [
      { year: 'Year 8', title: 'Published Analysis', description: 'Published an article on nuanced inference techniques.' },
      { year: 'Year 8', title: 'Lead Workshops', description: 'Led workshops training others in critical thinking.' }
    ]
  },
  {
    name: 'Senior Researcher',
    stage: 'Year 9 - Thought Leader',
    neuralParams: {
      logicalDepth: 5.2,
      abstractionLevel: 1.05,
      creativityFactor: 1.15,
      ambiguityTolerance: 0.32,
      metaLearningRate: 0.28,
      reasoningComplexity: 4.4,
      cognitiveDiversity: 0.85,
      patternRecognition: 0.98,
      logicalConsistency: 0.97,
      adaptiveThreshold: 0.9
    },
    achievements: [
      { year: 'Year 9', title: 'Methodological Innovation', description: 'Introduced novel meta-learning adjustments for reasoning systems.' },
      { year: 'Year 9', title: 'Mentorship', description: 'Mentored junior analysts and established training tracks.' }
    ]
  },
  {
    name: 'Principal Investigator',
    stage: 'Year 10 - Visionary',
    neuralParams: {
      logicalDepth: 6.0,
      abstractionLevel: 1.2,
      creativityFactor: 1.3,
      ambiguityTolerance: 0.36,
      metaLearningRate: 0.35,
      reasoningComplexity: 5.0,
      cognitiveDiversity: 0.92,
      patternRecognition: 1.0,
      logicalConsistency: 0.99,
      adaptiveThreshold: 0.95
    },
    achievements: [
      { year: 'Year 10', title: 'Legacy Systems', description: 'Built enduring training systems and knowledge banks for future learners.' },
      { year: 'Year 10', title: 'Cross-Disciplinary Impact', description: 'Applied reasoning frameworks across domains (ethics, law, engineering).' }
    ]
  },
  {
    name: 'Cognitive Architect',
    stage: 'Career - Systems Builder',
    neuralParams: {
      logicalDepth: 7.0,
      abstractionLevel: 1.4,
      creativityFactor: 1.45,
      ambiguityTolerance: 0.42,
      metaLearningRate: 0.4,
      reasoningComplexity: 5.6,
      cognitiveDiversity: 0.98,
      patternRecognition: 1.0,
      logicalConsistency: 0.995,
      adaptiveThreshold: 0.98
    },
    achievements: [
      { year: 'Mid Career', title: 'Architected TIS', description: 'Designed large-scale architectures for self-improving reasoning agents.' },
      { year: 'Mid Career', title: 'Standards Contributor', description: 'Contributed to evaluation standards for automated reasoning.' }
    ]
  },
  {
    name: 'Ethics & Policy Lead',
    stage: 'Career - Societal Steward',
    neuralParams: {
      logicalDepth: 6.3,
      abstractionLevel: 1.35,
      creativityFactor: 1.25,
      ambiguityTolerance: 0.5,
      metaLearningRate: 0.38,
      reasoningComplexity: 5.2,
      cognitiveDiversity: 0.9,
      patternRecognition: 0.98,
      logicalConsistency: 0.99,
      adaptiveThreshold: 0.9
    },
    achievements: [
      { year: 'Late Career', title: 'Policy Frameworks', description: 'Shaped governance frameworks for autonomous reasoning in public domains.' },
      { year: 'Late Career', title: 'Public Engagement', description: 'Translated complex reasoning concepts for broad audiences.' }
    ]
  },
  {
    name: 'Professor Emeritus',
    stage: 'Lifetime - Legacy',
    neuralParams: {
      logicalDepth: 5.8,
      abstractionLevel: 1.25,
      creativityFactor: 1.1,
      ambiguityTolerance: 0.48,
      metaLearningRate: 0.2,
      reasoningComplexity: 4.8,
      cognitiveDiversity: 0.85,
      patternRecognition: 0.95,
      logicalConsistency: 0.98,
      adaptiveThreshold: 0.9
    },
    achievements: [
      { year: 'Career End', title: 'Lifetime Contributions', description: 'A lifetime of advancing critical reasoning and mentoring generations.' },
      { year: 'Career End', title: 'Archive', description: 'Curated a comprehensive, high-quality question and pedagogy archive.' }
    ]
  }
];
