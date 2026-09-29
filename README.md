# KnitCode

KnitCode is a prototype for analyzing and visualizing relationships inside a codebase.

## Initial goal

The first milestone is to analyze a small Python project and extract:

- function definitions
- function calls
- caller → callee relationships
- source locations

## Structure

```text
knitcode/
├── analyzer/
│   ├── parser.py
│   ├── visitor.py
│   ├── resolver.py
│   └── graph.py
├── git_analyzer/
│   ├── history.py
│   └── cochange.py
├── backend/
│   └── api.py
├── frontend/
├── tests/
│   ├── fixtures/
│   │   └── toy_project/
│   │       ├── main.py
│   │       ├── service.py
│   │       ├── payment.py
│   │       └── database.py
│   └── test_parser.py
└── README.md
```

## Toy project call structure

```text
main.py
  └── create_order() [service.py]
        ├── calculate_price() [payment.py]
        └── save_order() [database.py]
```

Start implementation from `analyzer/parser.py` and `analyzer/visitor.py`.
