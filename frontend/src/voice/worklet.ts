/**
 * AudioWorklet that runs off the main thread: collects mic frames and posts ~100 ms batches
 * of float samples (at the context rate) to the page, which converts them to PCM 16 kHz.
 * Loaded from a Blob URL so the bundler does not need a separate worklet entry.
 */
export const WORKLET_SOURCE = `
class MiaCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buf = []; this.size = 0; this.target = Math.round(sampleRate / 10); }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      this.buf.push(new Float32Array(ch));
      this.size += ch.length;
      if (this.size >= this.target) {
        const out = new Float32Array(this.size);
        let o = 0;
        for (const b of this.buf) { out.set(b, o); o += b.length; }
        this.port.postMessage(out, [out.buffer]);
        this.buf = []; this.size = 0;
      }
    }
    return true;
  }
}
registerProcessor("mia-capture", MiaCapture);
`;

export function workletUrl(): string {
  return URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: "application/javascript" }));
}
