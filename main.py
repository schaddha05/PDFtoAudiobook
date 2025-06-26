import sys
from io import BytesIO
from pathlib import Path
import re 
import PyPDF2
from pydub import AudioSegment
from google.cloud import texttospeech

def extract_text(pdf_path):
    """Return the full text of a PDF as one big string."""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        raw = "\n".join(page.extract_text() or "" for page in reader.pages)
    clean = re.sub(r'\s+', ' ', raw).strip()
    return clean

def chunk_text(text, max_chars=4500):
    """Split a long string into ≤ max_chars pieces."""
    sentences = re.split(r'(?<=[\.\?!])\s+', text)
    chunks, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 1 > max_chars:
            chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)   
    return chunks

def synthesize_chunks_to_segments(chunks, voice_name="en-US-Wavenet-D", rate=1.0, pitch=0.0):
    """Call Google TTS on each chunk and return a list of AudioSegment."""
    client = texttospeech.TextToSpeechClient()
    segments = []

    for idx, chunk in enumerate(chunks, 1):
        # build request
        input_text = texttospeech.SynthesisInput(text=chunk)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=voice_name,
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )

        audio_cfg = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=rate,
            pitch=pitch
        )

        # call API
        resp = client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=audio_cfg
        )

        # load into pydub
        seg = AudioSegment.from_file(BytesIO(resp.audio_content), format="mp3")
        segments.append(seg)
        print("Chunk %d/%d synthesized (%d ms)" % (idx, len(chunks), len(seg)))

    return segments


def pdf_to_single_mp3(pdf_path, out_mp3, voice_name):
    print("→ extracting text…")
    text = extract_text(pdf_path)

    print("→ chunking text…")
    chunks = chunk_text(text)
    print(chunks)
    print("→ synthesizing %d chunk(s) with voice %s…" % (len(chunks), voice_name))
    segments = synthesize_chunks_to_segments(chunks, voice_name)

    print("→ concatenating audio…")
    full_audio = AudioSegment.empty()
    for seg in segments:
        full_audio += seg

    print("→ exporting %s…" % out_mp3)
    full_audio.export(out_mp3, format="mp3")
    print("✅ Done!")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python main.py <input.pdf> <output.mp3> [<voice-name>]")
        sys.exit(1)

    pdf_file = sys.argv[1]
    out_file = sys.argv[2]
    voice    = sys.argv[3] if len(sys.argv) > 3 else "en-US-Wavenet-D"

    pdf_to_single_mp3(pdf_file, out_file, voice)
