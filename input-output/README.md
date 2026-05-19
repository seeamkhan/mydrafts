# QR Air-Gap File Transfer

Byte-perfect file transfer between two machines using only the screen and a camera. No network, no cables, no USB.

- **Input machine**: holds the source file. Its browser turns the file into animated QR codes on screen.
- **Output machine**: has a camera. Its browser reads the QR codes and rebuilds the file.

The rebuilt file is verified with a **SHA-256 hash**, so if it saves, it is identical to the source byte-for-byte.

## How it works

```
   ┌──────────────────────┐                         ┌──────────────────────┐
   │    INPUT MACHINE     │                         │   OUTPUT MACHINE     │
   │   (runs input.html)  │                         │  (runs output.html)  │
   │                      │                         │                      │
   │   file ──► bytes     │                         │     camera ──► QR    │
   │     │                │      animated QR        │       │              │
   │     ▼                │  ───────────────────►   │       ▼              │
   │   base64 ──► chunks  │   screen → camera       │     decode chunks    │
   │     │                │     (no network)        │       │              │
   │     ▼                │                         │       ▼              │
   │   draw QR loop       │                         │   reassemble bytes   │
   │                      │                         │       │              │
   │                      │                         │       ▼              │
   │                      │                         │   SHA-256 verify     │
   │                      │                         │       │              │
   │                      │                         │       ▼              │
   │                      │                         │   save file ✓        │
   └──────────────────────┘                         └──────────────────────┘
```

## Why this is byte-perfect

Each QR contains base64-encoded chunks of the raw file bytes. The output machine verifies the SHA-256 hash before saving. If the hash matches, the file is **identical to the source, byte for byte**. If not, the receiver keeps scanning so the next loop fixes it.

This works for **any file type**: `.py`, `.md`, `.json`, `.png`, `.zip`, anything.

## What leaves the input machine

**Nothing.** Both HTML files have all libraries inlined. Zero network calls.

The file you pick stays in browser memory only. It is read by JavaScript, encoded to QR codes, displayed on screen. No upload, no fetch, no remote anything. You can verify in browser DevTools Network tab — zero requests.

## Speed

- 800 bytes per QR frame, 4 frames per second ≈ 3 KB/sec
- A 5 KB file: ~2 seconds per loop
- A 50 KB file: ~20 seconds per loop
- Hash verifies once one full loop completes

## Input machine setup (no admin needed)

1. Save `input.html` anywhere on the input machine
2. Double-click to open in any modern browser (Chrome, Edge, Safari, Firefox)
3. Pick your file
4. Click **Start Transmission**
5. QR codes start animating

## Output machine setup

1. Save `output.html` to the output machine
2. Open in any modern browser
3. Click **Start Camera** and allow camera permission
4. Pick your camera (built-in webcam works fine)
5. Point camera at the input machine's screen, about 30 to 50 cm away
6. File auto-downloads when the hash verifies

## Tuning if needed

On the sender page you can adjust:

- **Frame delay (ms)**: Higher = more reliable, slower. Default 250ms. If you miss frames, try 400ms.
- **Chunk size (bytes)**: Lower = smaller QR codes, easier to scan. Default 800. If camera struggles, try 400.
- **QR size (px)**: Bigger QR codes scan from further away. Default 600.

## Troubleshooting

**Camera reads nothing:**
- Move camera closer (~30 cm)
- Increase QR size to 800 px
- Reduce chunk size to 400
- Increase input machine display brightness

**Some chunks never arrive:**
- The transmission auto-loops. Leave it running; missing chunks fill in on the next loop.

**Hash mismatch:**
- Receiver auto-resets chunks but keeps the header. Next loop fixes it. No action needed.

## Protocol

**Input side (`input.html`):**
1. Read file bytes, compute SHA-256
2. Base64-encode bytes, split into 800-char chunks
3. Header packet: `H|filename|hash|totalChunks|originalSize`
4. Data packets: `D|index|data`
5. Display each as QR, loop forever until stopped

**Output side (`output.html`):**
1. Capture camera frames, decode QR with jsQR
2. Parse packet type (`H` or `D`)
3. Accumulate chunks by index
4. When all chunks received, concatenate, base64-decode
5. Compute SHA-256, compare to header hash
6. Match → save file. No match → reset chunks, keep listening.

The hash is the guarantee.
