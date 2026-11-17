import { INPUT_RATE, downsample, floatTo16 } from "./pcm";
import { workletUrl } from "./worklet";

/**
 * Records the visitor's answer locally (spec 5.6): the microphone opens only on start() and
 * closes on stop(). Nothing leaves the browser until the visitor clicks Enviar.
 */
export class Recorder {
  private stream: MediaStream | null = null;
  private ctx: AudioContext | null = null;
  private parts: Int16Array[] = [];

  async start(): Promise<void> {
    this.parts = [];
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
    this.ctx = new AudioContext();
    const url = workletUrl();
    await this.ctx.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const node = new AudioWorkletNode(this.ctx, "mia-capture");
    this.ctx.createMediaStreamSource(this.stream).connect(node);
    const rate = this.ctx.sampleRate;
    node.port.onmessage = (e: MessageEvent<Float32Array>) => {
      this.parts.push(floatTo16(downsample(e.data, rate, INPUT_RATE)));
    };
  }

  /** Stops and closes the microphone; returns the whole recording as PCM 16 kHz mono. */
  stop(): Int16Array {
    this.release();
    const total = this.parts.reduce((n, p) => n + p.length, 0);
    const out = new Int16Array(total);
    let offset = 0;
    for (const part of this.parts) {
      out.set(part, offset);
      offset += part.length;
    }
    this.parts = [];
    return out;
  }

  release(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close().catch(() => {});
    this.stream = null;
    this.ctx = null;
  }
}

/** Plays a local recording (PCM 16 kHz) so the visitor can listen before sending. */
export function playRecording(pcm: Int16Array, onEnded: () => void): () => void {
  const ctx = new AudioContext({ sampleRate: INPUT_RATE });
  const buffer = ctx.createBuffer(1, Math.max(1, pcm.length), INPUT_RATE);
  const channel = buffer.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;
  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  source.onended = () => {
    void ctx.close().catch(() => {});
    onEnded();
  };
  source.start();
  return () => {
    source.onended = null;
    try {
      source.stop();
    } catch {
      // already stopped
    }
    void ctx.close().catch(() => {});
  };
}

export function seconds(pcm: Int16Array): number {
  return Math.round(pcm.length / INPUT_RATE);
}
