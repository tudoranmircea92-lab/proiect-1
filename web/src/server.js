import express from 'express';
import path from 'path';
import fs from 'fs/promises';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

let liveProcess = null;
let lastConfig = null;
let logs = [];

function pushLog(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  logs.push(line);
  if (logs.length > 500) logs = logs.slice(-500);
}

app.get('/api/status', (_req, res) => {
  res.json({
    running: !!liveProcess,
    pid: liveProcess?.pid ?? null,
    lastConfig,
    logs: logs.slice(-120)
  });
});

app.get('/api/browse', async (req, res) => {
  const requestedPath = String(req.query.path || '').trim();
  const browsePath = requestedPath || process.cwd();
  try {
    const entries = await fs.readdir(browsePath, { withFileTypes: true });
    const items = await Promise.all(entries.map(async (entry) => {
      const fullPath = path.join(browsePath, entry.name);
      try {
        const stat = await fs.stat(fullPath);
        return {
          name: entry.name,
          path: fullPath,
          isDirectory: entry.isDirectory(),
          isFile: entry.isFile(),
          mtime: stat.mtime.toISOString()
        };
      } catch {
        return {
          name: entry.name,
          path: fullPath,
          isDirectory: entry.isDirectory(),
          isFile: entry.isFile(),
          mtime: null
        };
      }
    }));

    res.json({
      ok: true,
      path: browsePath,
      parent: path.dirname(browsePath),
      items: items.sort((a, b) => Number(b.isDirectory) - Number(a.isDirectory) || a.name.localeCompare(b.name))
    });
  } catch (error) {
    res.status(200).json({
      ok: false,
      path: browsePath,
      error: error?.message || 'Unable to browse path',
      items: []
    });
  }
});

app.post('/api/start', (req, res) => {
  if (liveProcess) {
    return res.status(400).json({ error: 'Pipeline already running.' });
  }

  const {
    pythonExe = 'python',
    optoplexDir,
    processDir,
    dbPath,
    pollSeconds = 10,
    matchWindowMinutes = 10,
    archiveDir,
    logFile,
    oneShot = false
  } = req.body || {};

  if (!optoplexDir || !processDir || !dbPath) {
    return res.status(400).json({ error: 'optoplexDir, processDir, dbPath sunt obligatorii.' });
  }

  const args = [
    '-m', 'scripts.run_live_db',
    '--optoplex-dir', optoplexDir,
    '--process-dir', processDir,
    '--db-path', dbPath,
    '--poll-seconds', String(pollSeconds),
    '--match-window-minutes', String(matchWindowMinutes)
  ];

  if (archiveDir) {
    args.push('--archive-dir', archiveDir);
  }
  if (logFile) {
    args.push('--log-file', logFile);
  }
  if (oneShot) {
    args.push('--one-shot');
  }

  liveProcess = spawn(pythonExe, args, {
    cwd: path.join(__dirname, '..', '..'),
    stdio: ['ignore', 'pipe', 'pipe']
  });

  lastConfig = { pythonExe, optoplexDir, processDir, dbPath, pollSeconds, matchWindowMinutes, archiveDir, logFile, oneShot };
  pushLog(`START cmd: ${pythonExe} ${args.join(' ')}`);

  liveProcess.stdout.on('data', (d) => pushLog(`OUT ${d.toString().trim()}`));
  liveProcess.stderr.on('data', (d) => pushLog(`ERR ${d.toString().trim()}`));

  liveProcess.on('exit', (code, signal) => {
    pushLog(`EXIT code=${code} signal=${signal}`);
    liveProcess = null;
  });

  return res.json({ ok: true });
});

app.post('/api/stop', (_req, res) => {
  if (!liveProcess) {
    return res.status(400).json({ error: 'Pipeline not running.' });
  }
  liveProcess.kill('SIGTERM');
  pushLog('STOP requested');
  return res.json({ ok: true });
});

app.listen(PORT, () => {
  console.log(`UI server running on http://localhost:${PORT}`);
});
