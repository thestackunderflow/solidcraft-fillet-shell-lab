"""Pin every file a card cites to the lab's HEAD commit: video/panel-sources.json with the sha256 of the committed blob
(git show <commit>:<path>, so a Windows working-copy line ending can never slip in). Fails if the working copy differs.

    python video/pin_sources.py     (on the host: needs git; run right after the commit that holds the sources)
"""
import hashlib
import json
import os
import subprocess
import sys

LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
PATHS = [
    'out/steps/batch-shell-then-fillet.jsonl', 'out/steps/batch-fillet-then-shell.jsonl', 'out/steps/batch-replies.json',
    'out/steps/run-shell-then-fillet.json', 'out/steps/run-fillet-then-shell.json', 'out/set_parameter/transcript.jsonl',
    'steps/shell-then-fillet.json', 'steps/fillet-then-shell.json',
    'out/probe/0.17.0/FS-10-1/measure.json', 'out/probe/0.17.0/SF-6-1/batch2_reply.json',
    'out/probe/0.17.0/SF-offered-1/batch2_reply.json', 'out/probe/0.17.0/SF-10-1/batch2_reply.json',
    'out/probe/SUMMARY.json', 'out/runs/SCORES.json', 'out/runs/BUDGET.log', 'out/evidence/numbers.json',
    'out/evidence/refusal.txt', 'claude-run/run.sh',
    'video/terminal-proof.txt', 'video/terminal-runs.txt', 'video/terminal-prompts.txt', 'video/terminal-refusal-clause.txt',
    'video/rule-card.txt', 'video/toolcalls.json', 'video/json-cards.json',
    'video/frames/frame0-both-boxes.png', 'video/frames/frame0-both-boxes.script.json',
    'video/frames/section-shell-only-corner.png', 'video/frames/section-FS-10-corner.png',
    'video/frames/section-SF-6-corner.png', 'video/frames/section-SF-6.82-corner.png',
    'video/frames/section-FS-10.png', 'video/frames/section-SF-6.png', 'video/frames/iso-FS-10.png',
    'video/frames/iso-shell-only.png',
]


def main():
    git = lambda *a: subprocess.run(['git', '-C', LAB, *a], capture_output=True, check=True).stdout  # noqa: E731
    commit = git('rev-parse', '--short', 'HEAD').decode().strip()
    sources, bad = [], []
    for p in PATHS:
        blob = git('show', f'{commit}:{p}')
        with open(os.path.join(LAB, p), 'rb') as f:
            if f.read() != blob:
                bad.append(p)
        sources.append({'path': p, 'pin': f'solidcraft-fillet-shell-lab@{commit}:{p}', 'sha256': hashlib.sha256(blob).hexdigest()})
    if bad:
        sys.exit(f'working copy differs from {commit}: {bad}')
    with open(os.path.join(LAB, 'video', 'panel-sources.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'lab': 'solidcraft-fillet-shell-lab', 'commit': commit,
                   'note': 'every card pins solidcraft-fillet-shell-lab@<commit>:<path>; sha256 of the committed blob',
                   'sources': sources}, f, indent=1)
        f.write('\n')
    print(commit, len(sources))


if __name__ == '__main__':
    main()
