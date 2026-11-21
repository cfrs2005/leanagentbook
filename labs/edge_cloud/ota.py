"""Local teaching OTA: signed metadata, immutable blobs, atomic pointer, recovery.

Single updater only. Ed25519 keys are generated in memory by the demonstration.
This is not a TUF implementation or a device firmware updater.
"""
import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def cohort(device_id, percent):
    if not 0 <= percent <= 100:
        raise ValueError('Invalid rollout percentage')
    return int(digest(device_id.encode())[:8], 16) % 100 < percent


class Store:
    def __init__(self, root, public_key, contract='features16-logits3-v1'):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_key = public_key
        self.contract = contract
        self.pointer = self.root / 'active.json'

    def state(self):
        return json.loads(self.pointer.read_text()) if self.pointer.exists() else {
            'active': None, 'previous': None, 'pending': False, 'highest': 0}

    def recover(self):
        state = self.state()
        if state['pending']:
            state['active'] = state['previous']
            state['pending'] = False
            atomic_json(self.pointer, state)
        return state

    def active_bytes(self):
        item = self.state()['active']
        return (self.root / (item['sha256'] + '.onnx')).read_bytes() if item else None

    def install(self, metadata, signature, payload, health, *, online=True,
                device_id='demo-001', crash=None):
        if not online:
            return 'offline-kept-local'
        # Authentication precedes all metadata-driven writes.
        self.public_key.verify(signature, canonical(metadata))
        state = self.recover()
        if metadata['contract'] != self.contract or metadata['runtime'] != 'onnxruntime-cpu':
            raise ValueError('Incompatible model contract or runtime')
        version = metadata['version']
        if type(version) is not int or version <= state['highest']:
            raise ValueError('Stale version')
        if metadata['sha256'] != digest(payload) or metadata['size'] != len(payload):
            raise ValueError('Corrupt payload')
        if not cohort(device_id, metadata['percent']):
            return 'outside-canary'
        blob = self.root / (digest(payload) + '.onnx')
        tmp = self.root / 'download.tmp'
        with tmp.open('wb') as stream:
            stream.write(payload[:len(payload)//2] if crash == 'download' else payload)
            stream.flush()
            os.fsync(stream.fileno())
        if crash == 'download':
            raise InterruptedError('Interrupted partial download')
        os.replace(tmp, blob)
        # Pointer transaction records recovery before activation. A restarted
        # process must call recover() before serving requests.
        new = {'active': metadata, 'previous': state['active'], 'pending': True,
               'highest': version}
        atomic_json(self.pointer, new)
        if crash == 'activate':
            raise InterruptedError('Interrupted after activation')
        try:
            healthy = bool(health(blob))
        except Exception:
            healthy = False
        if not healthy:
            self.recover()
            return 'rolled-back'
        new['pending'] = False
        atomic_json(self.pointer, new)
        return 'activated'
