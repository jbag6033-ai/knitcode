# KnitCode

KnitCode is a Python static analysis prototype for extracting, resolving, and visualizing relationships within a codebase.

It analyzes Python source code using the Abstract Syntax Tree (AST), resolves caller–callee relationships across files and classes, constructs a call graph, and visualizes the resulting code relationships.

## Features

KnitCode currently supports:

- Python source parsing using `ast`
- Function and class definition extraction
- Import and `from ... import ...` analysis
- Function and method call extraction
- Caller → callee relationship resolution
- Cross-file call resolution
- Class inheritance analysis
- `self.method()` resolution
- `super().method()` resolution
- Explicit parent method resolution
- Constructor → `__init__` resolution
- Indirect calls through collected callables
- List comprehension call analysis
- Nested lambda scope handling
- Call graph generation
- Interactive HTML visualization
- Benchmark evaluation using Precision, Recall, and F1-score

## Analysis Pipeline

```text
Python Project
      │
      ▼
  parser.py
      │
      ▼
  visitor.py
      │
      ▼
 resolver.py
      │
      ▼
   graph.py
      │
      ├──────────────► evaluate.py
      │
      ▼
 visualize.py
      │
      ▼
Interactive Call Graph
```

### Components

- `parser.py`  
  Reads Python source files and converts them into ASTs using `ast.parse()`.

- `visitor.py`  
  Traverses AST nodes and extracts functions, classes, imports, calls, scopes, and source locations.

- `resolver.py`  
  Resolves extracted calls to their actual definitions across modules, classes, inheritance relationships, and scopes.

- `graph.py`  
  Builds the resolved caller → callee call graph.

- `visualize.py`  
  Generates an interactive HTML visualization of the analyzed call graph.

- `evaluate.py`  
  Compares KnitCode's resolved call edges against benchmark ground truth and calculates Precision, Recall, and F1-score.

## Project Structure

```text
knitcode/
├── analyzer/
│   ├── __init__.py
│   ├── parser.py
│   ├── visitor.py
│   ├── resolver.py
│   ├── graph.py
│   ├── visualize.py
│   └── evaluate.py
│
├── git_analyzer/
│   ├── history.py
│   └── cochange.py
│
├── backend/
│   └── api.py
│
├── frontend/
│
├── tests/
│   ├── fixtures/
│   ├── test_parser.py
│   └── test_advanced_project.py
│
├── .gitignore
└── README.md
```

## Benchmark

KnitCode was evaluated on the **Sublist3r** Python project using ground-truth call relationships from the PyAnalyzer benchmark.

### Result

| Metric | Result |
|---|---:|
| Ground-truth edges | 115 |
| True Positives | 115 |
| False Positives | 0 |
| False Negatives | 0 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| F1-score | 1.0000 |

KnitCode successfully resolved all 115 project-internal call edges included in the evaluated Sublist3r benchmark.

## Development Progress

The call-edge resolver was incrementally extended to handle increasingly complex Python patterns.

```text
Baseline
  ↓
Inheritance / self method resolution
  ↓
super() / explicit parent method resolution
  ↓
Constructor → __init__ resolution
  ↓
Callable collection / list comprehension resolution
  ↓
Cross-module import resolution
  ↓
Nested lambda scope resolution
```

The current implementation achieves:

```text
Precision = 1.0000
Recall    = 1.0000
F1-score  = 1.0000
```

on the evaluated Sublist3r project-internal call-edge benchmark.

## Usage

Run the analyzer from the project root.

### Generate a call graph

```bash
python -m analyzer.graph
```

### Generate an interactive visualization

```bash
python -m analyzer.visualize
```

### Run benchmark evaluation

```bash
python -m analyzer.evaluate
```

### Run tests

```bash
pytest
```

## Current Scope

KnitCode currently focuses on static analysis of Python projects.

The current benchmark result represents performance on the evaluated Sublist3r project and should not be interpreted as perfect call-graph resolution for arbitrary Python programs. Dynamic Python features such as runtime monkey patching, reflection, and dynamically generated calls may require additional analysis.