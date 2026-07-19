/**
 * Microphone capture that produces a 16-bit PCM WAV blob.
 *
 * The backend's speech-to-text expects plain WAV, but MediaRecorder gives
 * WebM/Opus — so we capture raw samples with the Web Audio API and encode
 * the WAV header ourselves.
 */

export class WavRecorder {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private sampleRate = 16_000;

  get isRecording(): boolean {
    return this.stream !== null;
  }

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.context = new AudioContext();
    this.sampleRate = this.context.sampleRate;
    this.chunks = [];

    const source = this.context.createMediaStreamSource(this.stream);
    // ScriptProcessor is deprecated but universally supported and fine
    // for short utterances; an AudioWorklet would be overkill here.
    this.processor = this.context.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      this.chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    source.connect(this.processor);
    this.processor.connect(this.context.destination);
  }

  /** Stop recording and return the captured audio as a 16-bit WAV blob. */
  async stop(): Promise<Blob> {
    this.processor?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    await this.context?.close();

    const blob = encodeWav(this.chunks, this.sampleRate);
    this.stream = null;
    this.context = null;
    this.processor = null;
    this.chunks = [];
    return blob;
  }
}

function encodeWav(chunks: Float32Array[], sampleRate: number): Blob {
  const totalSamples = chunks.reduce((sum, c) => sum + c.length, 0);
  const buffer = new ArrayBuffer(44 + totalSamples * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };

  // Standard 44-byte WAV header for mono 16-bit PCM
  writeString(0, "RIFF");
  view.setUint32(4, 36 + totalSamples * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, totalSamples * 2, true);

  let offset = 44;
  for (const chunk of chunks) {
    for (const sample of chunk) {
      const clamped = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, clamped * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([buffer], { type: "audio/wav" });
}

/** Play base64-encoded WAV audio; resolves when playback finishes. */
export function playBase64Wav(base64: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const audio = new Audio(`data:audio/wav;base64,${base64}`);
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("Audio playback failed"));
    audio.play().catch(reject);
  });
}
