"""Explicit project-local types for public API inputs; never import target code."""
from pathlib import PurePosixPath


def seed_entrypoints(resolver, definitions, inputs):
    config = resolver.entrypoints
    if config is None:
        return
    if not isinstance(config, dict) or config.get('version') != 1 or not isinstance(config.get('entrypoints'), list):
        raise ValueError('Entry points require version=1 and an entrypoints list')
    seeds = []
    def valid_path(path):
        if (not isinstance(path, str) or not path or '\\' in path
                or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts):
            raise ValueError('Entry point paths must be relative project paths')
    for entry in config['entrypoints']:
        if not isinstance(entry, dict) or not isinstance(entry.get('function'), str) or not isinstance(entry.get('parameters'), dict):
            raise ValueError('Each entry requires file, function and parameters')
        file, function = entry.get('file'), entry['function']
        valid_path(file)
        if (file, function) not in definitions:
            raise ValueError(f'Unknown entry point: {file}::{function}')
        node = resolver.file_results[file].function_nodes[function]
        parameters = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
        for parameter, types in entry['parameters'].items():
            if parameter not in parameters or not isinstance(types, list) or not types:
                raise ValueError(f'Invalid entry point parameter: {function}.{parameter}')
            for declared in types:
                if not isinstance(declared, dict) or not isinstance(declared.get('class'), str):
                    raise ValueError('Input types require file and class')
                valid_path(declared.get('file'))
                matches = [d for d in resolver.class_definitions.get(declared['class'], []) if d['file'] == declared['file']]
                if len(matches) != 1:
                    raise ValueError(f'Unknown or ambiguous input class: {declared}')
                seeds.append(((file, function), parameter, ('instance', declared['file'], declared['class'])))
    for entry, parameter, value in seeds:
        inputs[entry][parameter].add(value)
