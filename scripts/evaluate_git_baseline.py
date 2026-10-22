"""Re-evaluate the unchanged Git engine with today's full-oracle scoring adapter."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref',default='06422ca2f57cff436efdf6b415a597d5c547c986')
    parser.add_argument('--output',type=Path,default=ROOT/'validation/github_progress_2026_10_22/github_baseline')
    args=parser.parse_args()
    ref=subprocess.check_output(['git','rev-parse',args.ref],cwd=ROOT,text=True).strip()
    files=subprocess.check_output(['git','ls-tree','-r','--name-only',ref],cwd=ROOT,text=True).splitlines()
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        checkout=Path(tmp)
        for name in files:
            if '/' not in name and name.endswith('.py'):
                (checkout/name).write_bytes(subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT))
        # Import baseline main and its dependency modules before importing the
        # current scorer. The original engine is never edited or patched.
        driver=checkout/'evaluate_snapshot.py'
        driver.write_text('''import sys, json, runpy
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import main, object_flow
sys.path.insert(0, sys.argv[2])
from scripts import evaluate_paper as evaluation
evaluation.ROOT=Path(sys.argv[1])
sys.path.insert(0, sys.argv[1])
# Original default exports had no external-call graph. Do not add new-engine
# candidate inference to the original engine's baseline.
evaluation.build_external_call_graph=lambda symbols, graph: dict(nodes=[], edges=[], summary={})
reference=Path(sys.argv[2])/'validation/paper_2026_10_22/reference/compare_macro_benchmark_cg.py'
scorer=runpy.run_path(str(reference))
results=[]
for project in evaluation.PROJECTS:
    row=evaluation.evaluate(project, Path(sys.argv[3])/project, scorer)
    print(json.dumps(row),flush=True)
    results.append(row)
(Path(sys.argv[3])/'summary.json').write_text(json.dumps(dict(commit=sys.argv[4], reference_script_sha256=evaluation.sha(reference), results=results),indent=2)+'\\n')
''')
        subprocess.run([sys.executable,str(driver),str(checkout),str(ROOT),str(args.output),ref],check=True,cwd=checkout)


if __name__=='__main__':main()
