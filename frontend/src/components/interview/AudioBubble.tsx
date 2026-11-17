import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { SpeakerLabel } from "@/components/interview/SpeakerLabel";
import type { Persona } from "@/lib/types";
import { playRecording, seconds } from "@/voice/recorder";

/** Spec 5.6: the visitor's voice answer as an audio message bubble (local recording only). */
export function AudioBubble({ pcm, persona }: { pcm: Int16Array; persona: Persona }) {
  const [playing, setPlaying] = useState(false);
  const stopRef = useRef<(() => void) | null>(null);
  useEffect(() => () => stopRef.current?.(), []);
  const total = seconds(pcm);

  function toggle() {
    if (playing) {
      stopRef.current?.();
      setPlaying(false);
      return;
    }
    setPlaying(true);
    stopRef.current = playRecording(pcm, () => setPlaying(false));
  }

  return (
    <div className="flex flex-col items-start gap-2" data-testid="audio-bubble">
      <SpeakerLabel speaker="candidate" persona={persona} />
      <button
        type="button"
        onClick={toggle}
        aria-label={playing ? "Pausar sua resposta" : "Ouvir sua resposta"}
        className="flex items-center gap-3 rounded-full border border-border bg-card px-4 py-2"
      >
        {playing ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
        <span className="flex h-6 items-end gap-0.5" aria-hidden="true">
          {[3, 5, 2, 6, 4, 6, 3, 5, 2, 4, 6, 3].map((h, i) => (
            <span key={i} className="w-1 rounded-full bg-muted-foreground" style={{ height: `${h * 4}px` }} />
          ))}
        </span>
        <span className="font-mono text-small tabular-nums text-muted-foreground">
          {`${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`}
        </span>
      </button>
    </div>
  );
}
