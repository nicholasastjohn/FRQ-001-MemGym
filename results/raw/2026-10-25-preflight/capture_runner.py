import datetime, hashlib, json, os, pathlib, platform, shlex, subprocess, sys, time
BASE = pathlib.Path('/Users/nick/Documents/Codex/2026-10-25/referenced-chatgpt-conversation-this-is-an/work')
OUT = BASE/'FRQ-001-MemGym/results/raw/2026-10-25-preflight'
UPSTREAM = BASE/'MemGym'

def run(label, args, cwd=UPSTREAM, timeout=None, capture_env=True):
    env=os.environ.copy()
    removed=[]
    for key in list(env):
        if ('API_KEY' in key or key in {'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','RUN_INTEGRATION_TESTS','LITELLM_MASTER_KEY','AZURE_API_KEY','AZURE_AD_TOKEN','ANTHROPIC_AUTH_TOKEN','OPENAI_ACCESS_TOKEN'}):
            removed.append(key); env.pop(key,None)
    env['RUN_INTEGRATION_TESTS']='0'
    env['TOKENIZERS_PARALLELISM']='false'
    env['LITELLM_LOCAL_MODEL_COST_MAP']='True'
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    t=time.monotonic()
    path=OUT/(label+'.log')
    with path.open('w') as f:
        f.write('$ '+shlex.join([str(a) for a in args])+'\n')
        f.write('cwd: '+str(cwd)+'\nstart_utc: '+start+'\n\n'); f.flush()
        try:
            proc=subprocess.run([str(a) for a in args],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
            code=proc.returncode
        except subprocess.TimeoutExpired:
            code=124; f.write('\nTIMEOUT\n')
        end=datetime.datetime.now(datetime.timezone.utc).isoformat()
        elapsed=round(time.monotonic()-t,3)
        f.write('\nend_utc: '+end+'\nexit_code: '+str(code)+'\nelapsed_seconds: '+str(elapsed)+'\n')
    meta=dict(label=label,argv=[str(a) for a in args],command=shlex.join([str(a) for a in args]),cwd=str(cwd),start_utc=start,end_utc=end,elapsed_seconds=elapsed,exit_code=code,log=path.name,env_controls={'RUN_INTEGRATION_TESTS':'0','TOKENIZERS_PARALLELISM':'false','LITELLM_LOCAL_MODEL_COST_MAP':'True','removed_credential_variable_names': sorted(removed)})
    with (OUT/'commands.jsonl').open('a') as f: f.write(json.dumps(meta,sort_keys=True)+'\n')
    print(json.dumps(meta,sort_keys=True),flush=True)
    return code

if __name__=='__main__':
    label=sys.argv[1]; argv=json.loads(sys.argv[2]); sys.exit(run(label,argv))
