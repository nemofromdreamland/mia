import { OUTPUT_RATE, base64ToInt16, int16ToFloat } from "./pcm";

/** Plays MIA's PCM 24 kHz in order, without gaps or overlap; `stop()` cuts it at once. */
export class Player {
  private ctx: AudioContext;
  private next = 0;
  private sources = new Set<AudioBufferSourceNode>();
  onIdle: () => void = () => {};

  constructor(ctx?: AudioContext) {
    this.ctx = ctx ?? new AudioContext({ sampleRate: OUTPUT_RATE });
  }

  get playing(): boolean {
    return this.sources.size > 0;
  }

  play(data: string): void {
    const samples = int16ToFloat(base64ToInt16(data));
    if (samples.length === 0) return;
    const buffer = this.ctx.createBuffer(1, samples.length, OUTPUT_RATE);
    buffer.getChannelData(0).set(samples);
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.ctx.destination);
    const at = Math.max(this.ctx.currentTime, this.next);
    source.start(at);
    this.next = at + buffer.duration;
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      if (this.sources.size === 0) this.onIdle();
    };
  }

  stop(): void {
    for (const source of this.sources) {
      source.onended = null;
      try {
        source.stop();
      } catch {
        // already stopped
      }
    }
    this.sources.clear();
    this.next = 0;
  }

  async resume(): Promise<void> {
    if (this.ctx.state === "suspended") await this.ctx.resume();
  }

  close(): void {
    this.stop();
    void this.ctx.close().catch(() => {});
  }
}
