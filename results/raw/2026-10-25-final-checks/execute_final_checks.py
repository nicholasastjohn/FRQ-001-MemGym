from pathlib import Path
import sys
root=Path(__file__).resolve().parent/'FRQ-001-MemGym'
sys.path.insert(0,str(root/'scripts'))
from reproduce import Evidence, parser, snapshot
python=str(root.parent/'venvs/memgym/bin/python')
args=parser().parse_args(['preflight','--upstream',str(root.parent/'MemGym'),'--python',python,'--output',str(root/'results/raw/2026-10-25-final-checks')])
run=Evidence(args)
(run.output/'execute_final_checks.py').write_bytes(Path(__file__).read_bytes())
snapshot(run)
run.command('harness_safety_tests',[python,'-m','unittest','discover','-s',str(root/'scripts/tests'),'-v'],offline=False)
run.command('frq_diff_check',['git','-C',str(root),'diff','--check'],offline=False)
raise SystemExit(run.finish())
