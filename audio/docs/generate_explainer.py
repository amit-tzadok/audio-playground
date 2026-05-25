"""
Generate a "for dummies" PDF explainer for the speaker diarization pipeline.
"""

from fpdf import FPDF
from pathlib import Path


FONT_DIR = "/System/Library/Fonts/Supplemental"
FONT_UNICODE = "/Library/Fonts/Arial Unicode.ttf"


class PDF(FPDF):
    def _load_fonts(self):
        self.add_font("Arial", style="",  fname=f"{FONT_DIR}/Arial.ttf")
        self.add_font("Arial", style="B", fname=f"{FONT_DIR}/Arial Bold.ttf")
        self.add_font("Arial", style="I", fname=f"{FONT_DIR}/Arial Italic.ttf")
        self.add_font("Arial", style="BI", fname=f"{FONT_DIR}/Arial Bold Italic.ttf")
        self.add_font("ArialMono", style="",  fname=f"{FONT_DIR}/Andale Mono.ttf")

    def header(self):
        self.set_font("Arial", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "Speaker Diarization Pipeline — How It Works", align="R")
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def chapter_title(self, text, color=(30, 80, 160)):
        self.set_font("Arial", "B", 15)
        self.set_text_color(*color)
        self.ln(4)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*color)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def section_title(self, text):
        self.set_font("Arial", "B", 12)
        self.set_text_color(50, 50, 50)
        self.ln(3)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body(self, text):
        self.set_font("Arial", "", 10.5)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 6.5, text)
        self.ln(2)

    def bullet(self, items, indent=8):
        self.set_font("Arial", "", 10.5)
        self.set_text_color(30, 30, 30)
        for item in items:
            self.set_x(self.l_margin + indent)
            self.multi_cell(0, 6.5, f"-  {item}", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def code_block(self, lines):
        self.set_fill_color(240, 242, 246)
        self.set_draw_color(200, 205, 215)
        self.set_font("ArialMono", "", 9)
        self.set_text_color(20, 20, 80)
        self.ln(1)
        padding = 4
        x0 = self.l_margin
        w = self.w - self.l_margin - self.r_margin
        line_h = 5.5
        block_h = len(lines) * line_h + padding * 2
        self.rect(x0, self.get_y(), w, block_h, style="FD")
        self.set_y(self.get_y() + padding)
        for line in lines:
            self.set_x(x0 + padding)
            self.cell(w - padding * 2, line_h, line, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def callout(self, emoji, title, text, bg=(255, 248, 220), border=(220, 180, 50)):
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_font("Arial", "B", 10.5)
        self.set_text_color(80, 60, 0)
        self.ln(2)
        x0 = self.l_margin
        w = self.w - self.l_margin - self.r_margin
        # measure height
        self.set_font("Arial", "", 10)
        lines_needed = self.multi_cell(w - 8, 6, text, dry_run=True, output="LINES")
        block_h = 8 + len(lines_needed) * 6 + 6
        self.rect(x0, self.get_y(), w, block_h, style="FD")
        self.set_x(x0 + 4)
        self.set_font("Arial", "B", 10.5)
        self.cell(0, 8, f"{emoji}  {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_x(x0 + 4)
        self.set_font("Arial", "", 10)
        self.multi_cell(w - 8, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def pipeline_step(self, number, title, subtitle, description):
        self.set_fill_color(30, 80, 160)
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 11)
        self.ln(3)
        self.rect(self.l_margin, self.get_y(), 8, 8, style="F")
        y_before = self.get_y()
        self.set_x(self.l_margin)
        self.cell(8, 8, str(number), align="C")
        self.set_xy(self.l_margin + 11, y_before)
        self.set_text_color(20, 20, 100)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(self.l_margin + 11)
        self.set_font("Arial", "I", 9.5)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        self.set_font("Arial", "", 10.5)
        self.set_text_color(30, 30, 30)
        self.set_x(self.l_margin + 11)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 11, 6.5, description)
        self.ln(3)


def build():
    pdf = PDF(format="A4")
    pdf._load_fonts()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Title page block ─────────────────────────────────────────────────────
    pdf.set_fill_color(30, 80, 160)
    pdf.rect(0, 0, pdf.w, 52, style="F")
    pdf.set_y(12)
    pdf.set_font("Arial", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, "Speaker Diarization Pipeline", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 13)
    pdf.set_text_color(180, 210, 255)
    pdf.cell(0, 8, "A Plain-English Guide to How It All Works", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(150, 190, 240)
    pdf.cell(0, 7, "f0.py  -  speaker_splitter.py  -  pyannote / HuggingFace", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(60)

    # ── Big picture ──────────────────────────────────────────────────────────
    pdf.chapter_title("1.  The Big Picture")
    pdf.body(
        "Imagine you record a conversation between two people on a single microphone. "
        "You end up with one audio file where both voices are mixed together. "
        "The goal of this pipeline is to answer two questions:\n\n"
        "   A)  Who is speaking at each moment in time?\n"
        "   B)  Can we produce a separate audio file for each speaker?\n\n"
        "That is exactly what these two scripts do, in order:"
    )
    pdf.bullet([
        "f0.py  --  figures out WHO speaks WHEN (this is called diarization).",
        "speaker_splitter.py  --  uses that information to carve the audio into "
        "one file per speaker, with silence where the other person was talking.",
    ])

    pdf.callout(
        "[Tip]", "Analogy",
        "Think of a court transcript. A stenographer labels every line with the "
        "speaker's name. f0.py is the stenographer. speaker_splitter.py is the "
        "clerk who then collects all of one person's lines into a separate document.",
        bg=(235, 245, 255), border=(100, 160, 220),
    )

    # ── Pipeline overview ────────────────────────────────────────────────────
    pdf.chapter_title("2.  Step-by-Step Pipeline")

    pdf.pipeline_step(1, "Load the audio file", "load_wave_file()  in  f0.py",
        "The WAV file is read from disk using Python's built-in wave module. "
        "The raw bytes are converted to a numpy array of floating-point numbers "
        "between -1 and +1, one number per audio sample. "
        "If the file is stereo (two channels), only the left channel is kept. "
        "This gives us a simple list of numbers that represents the sound wave over time.")

    pdf.pipeline_step(2, "Run the AI diarization model", "Pipeline.from_pretrained()  in  f0.py",
        "This is the core of the whole system. A pre-trained neural network from "
        "pyannote (hosted on HuggingFace) analyses the audio and decides, for every "
        "fraction of a second, which speaker is most likely talking. "
        "It outputs a list of time segments, each tagged with a speaker label like "
        "SPEAKER_00 or SPEAKER_01. The model was trained on thousands of hours of "
        "real conversations, so it already understands what makes two voices different "
        "without any extra configuration from us.")

    pdf.pipeline_step(3, "Export a diarization JSON", "export_segments_json()  in  f0.py",
        "The segment list is written to a .json file next to the original audio. "
        "Each entry records the speaker label, a start time, and an end time in the "
        "format HH:MM:SS,mmm. This file is the handshake between the two scripts: "
        "f0.py writes it, speaker_splitter.py reads it.")

    pdf.pipeline_step(4, "Colour the waveform", "Visualization block  in  f0.py",
        "To let you visually verify the result, the audio waveform is drawn in "
        "matplotlib. The waveform is split into small chunks of 256 samples and each "
        "chunk is coloured according to which speaker owns that moment in time. "
        "A moving red cursor follows the playback position in real time.")

    pdf.pipeline_step(5, "Split the audio", "create_speaker_audio()  in  speaker_splitter.py",
        "For each unique speaker found in the JSON, a brand-new silent audio track "
        "is created with the same total length as the original. Then, for every "
        "segment belonging to that speaker, the corresponding slice of the real audio "
        "is copied (overlaid) into the silent track at the correct position. "
        "Everything else stays silent. The result is exported as a WAV file named "
        "output-audio-SPEAKER_00.wav, output-audio-SPEAKER_01.wav, and so on.")

    pdf.add_page()

    # ── f0.py deep dive ──────────────────────────────────────────────────────
    pdf.chapter_title("3.  f0.py  --  Deep Dive")

    pdf.section_title("3.1  Loading audio")
    pdf.body(
        "Audio files store sound as a sequence of numbers called samples. "
        "A sample rate of 16,000 Hz means there are 16,000 numbers per second. "
        "The load_wave_file() function opens the file, reads all the raw bytes, "
        "and converts them from 16-bit integers (the WAV format) to float32 values "
        "in the range [-1, 1] by dividing by the maximum possible value. "
        "Normalisation like this makes downstream processing more stable."
    )
    pdf.code_block([
        "audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)",
        "audio /= (np.max(np.abs(audio)) + 1e-8)   # normalise to [-1, 1]",
    ])

    pdf.section_title("3.2  Running pyannote")
    pdf.body(
        "The single most important line in the whole project is:"
    )
    pdf.code_block([
        'pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=...)',
        "diarization = pipeline(audio_file, num_speakers=2)",
    ])
    pdf.body(
        "Pipeline.from_pretrained() downloads (or loads from cache) a complete "
        "neural network that was trained by the pyannote team. Internally it runs "
        "three stages:\n\n"
        "   -  Voice Activity Detection (VAD)  --  find the parts of the audio that "
        "contain speech at all, discarding silence and background noise.\n\n"
        "   -  Speaker Embedding  --  for each short speech segment, compute a compact "
        "numerical fingerprint (a vector of ~256 numbers) that captures the unique "
        "characteristics of the voice in that segment.\n\n"
        "   -  Clustering  --  group the fingerprints so that segments from the same "
        "speaker end up in the same cluster. Each cluster becomes a speaker label."
    )
    pdf.callout(
        "[Info]", "What is a speaker embedding?",
        "A speaker embedding is like a voice fingerprint. Two segments from the same "
        "person will produce very similar vectors (close together in space). Two "
        "segments from different people will produce very different vectors (far apart). "
        "The model converts the messy audio signal into this clean mathematical "
        "representation so that standard clustering algorithms can separate the speakers.",
        bg=(240, 255, 240), border=(80, 160, 80),
    )

    pdf.section_title("3.3  Mapping segments to samples")
    pdf.body(
        "pyannote gives us time segments (e.g. 4.27s - 5.85s = SPEAKER_00). "
        "But for colouring the waveform, we need to know the speaker label for every "
        "single sample in the audio array. "
        "We create a time_axis array that maps each sample index to its time in seconds, "
        "then use numpy's searchsorted() to find where each segment boundary falls "
        "in that array, and fill in the speaker label for the whole range."
    )
    pdf.code_block([
        "time_axis = np.linspace(0, total_duration, len(audio_array))",
        "for start, end, speaker in segments:",
        "    i0 = np.searchsorted(time_axis, start)",
        "    i1 = np.searchsorted(time_axis, end)",
        "    sample_labels[i0:i1] = speaker_to_idx[speaker]",
    ])

    pdf.section_title("3.4  Timestamp format")
    pdf.body(
        "The JSON uses the format HH:MM:SS,mmm (hours, minutes, seconds, milliseconds). "
        "This is the standard subtitle format (SRT) and is also used by speaker_splitter.py. "
        "The seconds_to_timestamp() helper converts a plain float like 74.5 into "
        "00:01:14,500. The reverse conversion in speaker_splitter.py turns that string "
        "back into milliseconds (74500) so pydub can slice the audio precisely."
    )

    pdf.add_page()

    # ── speaker_splitter.py deep dive ────────────────────────────────────────
    pdf.chapter_title("4.  speaker_splitter.py  --  Deep Dive")

    pdf.section_title("4.1  Reading the JSON")
    pdf.body(
        "The script takes two command-line arguments: the original WAV file and the "
        "diarization JSON. It loads the JSON and collects all unique speaker labels "
        "found in the segments list. It then processes each speaker one at a time."
    )

    pdf.section_title("4.2  Building the silent base track")
    pdf.body(
        "pydub is used to handle audio at a higher level than raw numpy arrays. "
        "AudioSegment.from_wav() loads the full original audio. "
        "AudioSegment.silent() creates a new audio object of the same total duration "
        "filled with complete silence (all zeros). This silent track is the canvas "
        "on which the speaker's audio will be painted."
    )
    pdf.code_block([
        "audio = AudioSegment.from_wav(input_audio_path)",
        "silent_audio = AudioSegment.silent(duration=len(audio))",
    ])

    pdf.section_title("4.3  Overlaying the speaker's segments")
    pdf.body(
        "For each segment in the JSON that belongs to the target speaker, the "
        "timestamp is converted to milliseconds, the corresponding slice is cut from "
        "the original audio using Python's slice notation (audio[start_ms:end_ms]), "
        "and then placed onto the silent track at exactly the right position using "
        "overlay(). Because we started with silence, overlaying a real audio segment "
        "simply inserts it without any mixing."
    )
    pdf.code_block([
        "for segment in segments_data['segments']:",
        "    if segment['speaker'] == speaker_id:",
        "        start_ms = timestamp_to_milliseconds(segment['start'])",
        "        end_ms   = timestamp_to_milliseconds(segment['end'])",
        "        chunk = audio[start_ms:end_ms]",
        "        silent_audio = silent_audio.overlay(chunk, position=start_ms)",
    ])

    pdf.callout(
        "[!]", "Important limitation",
        "This approach can only separate speakers in time -- it cannot remove one "
        "person's voice from a moment when both people are speaking simultaneously. "
        "If Speaker A's voice bleeds into Speaker B's segment (e.g. background talking "
        "or overlapping speech), it will still appear in Speaker B's output file. "
        "True voice isolation requires a different class of model called a "
        "source separator (e.g. SepFormer).",
    )

    # ── HuggingFace section ──────────────────────────────────────────────────
    pdf.chapter_title("5.  The HuggingFace / pyannote Layer")

    pdf.section_title("5.1  What is HuggingFace Hub?")
    pdf.body(
        "HuggingFace Hub is a platform where researchers publish pre-trained AI models. "
        "Think of it like GitHub, but specifically for neural networks. "
        "A model is a file (or set of files) containing millions of numbers that were "
        "learned during a long training process on large datasets. "
        "By downloading a model from the Hub, you skip the training step entirely "
        "and use the results of someone else's months of compute."
    )
    pdf.bullet([
        "Pipeline.from_pretrained(model_id)  --  downloads the model files to your "
        "local cache (~/.cache/huggingface/) on the first run, then reuses them.",
        "The token (hf_...)  --  proves to HuggingFace that you agreed to the model's "
        "terms of use. Some models (like pyannote's) are gated: you must request "
        "access before the Hub will serve the files to you.",
        "After the first download everything runs fully offline -- no internet required.",
    ])

    pdf.section_title("5.2  What pyannote actually runs")
    pdf.body(
        "The pyannote speaker-diarization-3.1 pipeline is itself a composition of "
        "three smaller neural networks, each a separate HuggingFace model:"
    )
    pdf.bullet([
        "pyannote/segmentation-3.0  --  a transformer that runs on short windows of "
        "audio and outputs a probability for each window: is there speech here, "
        "and if so, how many speakers?",
        "pyannote/embedding  (wespeaker-voxceleb-resnet34-LM)  --  a ResNet-based "
        "network that converts a speech segment into a 256-dimensional embedding vector.",
        "pyannote/speaker-diarization-community-1  --  contains a PLDA model, "
        "a classical (non-neural) scoring method that refines how embeddings are "
        "compared to improve accuracy on real-world audio.",
    ])

    pdf.section_title("5.3  What a ResNet is (in plain English)")
    pdf.body(
        "A ResNet (Residual Network) is a type of deep neural network originally "
        "designed for image recognition. For audio, the raw waveform is first "
        "converted to a spectrogram (a 2-D image where one axis is time and the "
        "other is frequency). The ResNet then processes this image, layer by layer, "
        "learning to detect patterns -- pitch, timbre, speaking rhythm -- that "
        "are unique to a particular voice. The final layer outputs the 256-number "
        "embedding that summarises everything the network learned about that voice."
    )

    pdf.callout(
        "[Note]", "Why 256 numbers?",
        "256 is the dimensionality of the embedding space. It is a design choice: "
        "large enough to capture the richness of a human voice, small enough to "
        "cluster efficiently. Two embeddings from the same speaker will have a "
        "cosine similarity close to 1.0; two from different speakers will be much lower.",
        bg=(245, 240, 255), border=(120, 80, 200),
    )

    pdf.section_title("5.4  PLDA scoring")
    pdf.body(
        "PLDA (Probabilistic Linear Discriminant Analysis) is a statistical model "
        "that learns, from labelled training data, how much natural variation exists "
        "within a single speaker versus across different speakers. "
        "It adjusts the raw embedding comparisons to be more robust to things like "
        "microphone differences, background noise, and the speaker's emotional state. "
        "It is stored as a matrix file (xvec_transform.npz) and applied after the "
        "neural embedding step."
    )

    # ── How the algorithm separates speakers ─────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("6.  How the Algorithm Separates Speakers -- Step by Step")

    pdf.body(
        "This chapter goes inside the black box. When you call pipeline(audio_file), "
        "here is exactly what happens internally, in order."
    )

    pdf.section_title("Step 1 -- From waveform to spectrogram")
    pdf.body(
        "The raw audio is a one-dimensional list of numbers -- one pressure value per "
        "sample (16,000 per second). Neural networks cannot do much with this directly. "
        "The first transformation converts it into a mel spectrogram: a 2-D grid where "
        "the horizontal axis is time and the vertical axis is frequency (pitch). "
        "The value at each cell represents how much energy exists at that frequency at "
        "that moment in time."
    )
    pdf.body(
        "The 'mel' scale compresses high frequencies and expands low ones, mimicking "
        "how the human ear perceives pitch. This makes the spectrogram much more "
        "useful for voice analysis than a raw frequency grid would be."
    )
    pdf.callout(
        "[Tip]", "Think of it like sheet music",
        "In sheet music, time flows left to right and pitch flows bottom (low notes) "
        "to top (high notes). A mel spectrogram is the same idea, but instead of note "
        "symbols it shows the energy (volume) at every pitch at every moment. "
        "Every neural network in this pipeline reads this 'image' rather than the "
        "raw waveform.",
        bg=(235, 245, 255), border=(100, 160, 220),
    )

    pdf.section_title("Step 2 -- Voice Activity Detection (VAD)")
    pdf.body(
        "Before doing any speaker identification, the pipeline needs to know which "
        "parts of the audio actually contain speech. This is done by the "
        "pyannote/segmentation-3.0 model, a transformer-based neural network."
    )
    pdf.body(
        "The model slides a window (~10 seconds wide) across the spectrogram and for "
        "each window predicts, frame by frame:"
    )
    pdf.bullet([
        "Is there any speech here at all, or just silence / background noise?",
        "If yes, how many speakers appear to be active simultaneously (1 or 2+)?",
        "Where does the current speaker seem to change?",
    ])
    pdf.body(
        "The output is a timeline of speech segments with silence removed. "
        "This step is critical: it means the expensive embedding network in Step 3 "
        "only runs on frames that actually contain someone speaking, not on silence "
        "or music or background noise."
    )

    pdf.section_title("Step 3 -- Speaker Embedding: building a voice fingerprint")
    pdf.body(
        "This is the heart of the algorithm. For each speech segment identified in "
        "Step 2, the wespeaker ResNet-34 model computes a speaker embedding -- a "
        "vector of 256 numbers that acts as a compact fingerprint of the voice in "
        "that segment."
    )
    pdf.body(
        "Internally, the ResNet works like this:"
    )
    pdf.bullet([
        "The segment's mel spectrogram is treated exactly like an image and fed "
        "into a 34-layer deep convolutional neural network.",
        "Early layers detect simple patterns: edges in the frequency domain, "
        "basic pitch contours, short bursts of energy.",
        "Middle layers combine these into more complex patterns: formant shapes "
        "(the resonance frequencies of the vocal tract), speaking rhythm, "
        "breath patterns.",
        "Deep layers capture the most abstract characteristics: the overall "
        "acoustic 'texture' that is unique to a given person's voice.",
        "A pooling layer collapses the time dimension -- it computes the mean "
        "and standard deviation of the activations across all time steps -- "
        "giving a single fixed-size vector regardless of how long the segment is.",
        "A final linear projection reduces this to exactly 256 numbers.",
        "The vector is L2-normalized: scaled so its total length equals 1.0. "
        "This allows similarity to be measured purely by direction, not magnitude.",
    ])
    pdf.callout(
        "[Info]", "Why does L2-normalization matter?",
        "After normalization, all embedding vectors sit on the surface of a "
        "256-dimensional sphere. The angle between two vectors on this sphere "
        "is all that matters for comparison. Two segments from the same speaker "
        "will produce vectors pointing in nearly the same direction (cosine "
        "similarity close to 1.0). Two segments from different speakers will "
        "point in very different directions (cosine similarity much lower). "
        "This geometry is what makes clustering work reliably.",
        bg=(240, 255, 240), border=(80, 160, 80),
    )

    pdf.section_title("Step 4 -- PLDA: smarter similarity scoring")
    pdf.body(
        "Raw cosine similarity between embeddings works, but it is noisy. The same "
        "person sounds different when excited versus calm, or when speaking close "
        "to the microphone versus from across the room. PLDA (Probabilistic Linear "
        "Discriminant Analysis) fixes this."
    )
    pdf.body(
        "PLDA is a statistical model trained on a large labelled dataset of "
        "recordings where the speaker identity of every segment is known. "
        "From this data it learns two things:"
    )
    pdf.bullet([
        "Within-speaker variability: how much do two embeddings from the SAME "
        "person naturally differ from each other due to recording conditions, "
        "emotion, or speaking style?",
        "Between-speaker variability: how much do embeddings from DIFFERENT "
        "people differ on average?",
    ])
    pdf.body(
        "It uses this knowledge to transform the embedding space so that "
        "within-speaker differences shrink and between-speaker differences grow. "
        "The result is a PLDA score between any two segments -- a number that "
        "is much more reliable than raw cosine similarity for deciding whether "
        "two segments come from the same person."
    )
    pdf.body(
        "The transformation is stored as a matrix (xvec_transform.npz) and applied "
        "to every embedding before any comparisons are made. It is a classical "
        "linear algebra operation, not a neural network, so it is very fast."
    )

    pdf.section_title("Step 5 -- Agglomerative Hierarchical Clustering")
    pdf.body(
        "Now we have N embeddings (one per speech segment) and PLDA-adjusted "
        "similarity scores between every pair. The clustering algorithm groups "
        "them into speaker identities:"
    )
    pdf.bullet([
        "Start: treat every segment as its own cluster (N clusters total).",
        "Compute the similarity between all pairs of clusters.",
        "Find the two most similar clusters and merge them into one.",
        "Recompute similarities involving the new merged cluster.",
        "Repeat until the number of clusters equals num_speakers (2 in our case).",
    ])
    pdf.body(
        "This is called 'agglomerative' (bottom-up) clustering because it starts "
        "with many small clusters and merges upward, as opposed to 'divisive' "
        "(top-down) approaches that start with one cluster and split. "
        "The merging criterion -- how to compute the similarity of a merged "
        "cluster to others -- uses average linkage: the similarity between two "
        "clusters is the average of all pairwise similarities between their members."
    )
    pdf.callout(
        "[Tip]", "Analogy: sorting strangers into groups",
        "Imagine you have 50 short audio clips and you want to sort them into "
        "two piles by speaker. You start by listening to the two most similar "
        "clips and put them in the same pile. Then you keep finding the most "
        "similar remaining pair and grouping them. Eventually you end up with "
        "exactly two piles -- that is agglomerative clustering.",
        bg=(255, 248, 220), border=(220, 180, 50),
    )

    pdf.section_title("Step 6 -- Resolving overlaps")
    pdf.body(
        "After clustering, the raw output (speaker_diarization) may contain "
        "overlapping segments -- moments where two speakers are both active "
        "simultaneously. This is realistic (people do talk over each other), "
        "but speaker_splitter.py needs clean non-overlapping segments."
    )
    pdf.body(
        "The exclusive_speaker_diarization pass resolves this: for every "
        "overlapping moment it picks the speaker with the higher confidence "
        "score and assigns the entire frame to them. The other speaker's "
        "contribution at that moment is discarded. The result is a clean "
        "timeline where every moment in time belongs to exactly one speaker "
        "or to silence."
    )

    pdf.section_title("Why it sometimes fails")
    pdf.body(
        "Understanding the algorithm makes it easy to predict when it will struggle:"
    )
    pdf.bullet([
        "Similar voices: if two speakers have similar pitch, timbre, and rhythm, "
        "their embeddings will be close together in the 256-dimensional space and "
        "clustering may merge them into one cluster.",
        "Short segments: the ResNet needs at least a few seconds of speech to "
        "produce a reliable embedding. Very short utterances (under ~1 second) "
        "produce noisy fingerprints.",
        "Poor audio quality: microphone bleed, heavy reverb, or background music "
        "alter the spectrogram in ways that shift embeddings away from their "
        "true position, confusing the PLDA scoring.",
        "One speaker dominates: if one person speaks 90% of the time, the "
        "clustering may not gather enough evidence for the second speaker's "
        "cluster and may split the dominant speaker into two clusters instead.",
        "More speakers than expected: if num_speakers=2 is passed but three "
        "people speak, the algorithm is forced to squeeze three voices into "
        "two clusters, guaranteeing at least some mislabeling.",
    ])

    # ── Data flow diagram ────────────────────────────────────────────────────
    pdf.add_page()
    pdf.chapter_title("7.  Data Flow at a Glance")

    pdf.body("Here is how data moves through the system from start to finish:")
    pdf.ln(2)

    steps = [
        ("WAV file  (mixed audio)",          "60, 60, 60"),
        ("load_wave_file()  ->  numpy float32 array",  "30, 80, 160"),
        ("pyannote Pipeline  ->  VAD + Embedding + Clustering", "30, 80, 160"),
        ("DiarizeOutput  ->  list of (start, end, speaker)",     "30, 80, 160"),
        ("export_segments_json()  ->  .diarization.json",        "30, 80, 160"),
        ("speaker_splitter.py reads JSON",   "20, 120, 60"),
        ("For each speaker: silent_audio.overlay(chunk)", "20, 120, 60"),
        ("output-audio-SPEAKER_00.wav  +  output-audio-SPEAKER_01.wav", "60, 60, 60"),
    ]

    box_w = pdf.w - pdf.l_margin - pdf.r_margin
    for i, (label, color_str) in enumerate(steps):
        r, g, b = map(int, color_str.split(", "))
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B" if i in (0, len(steps) - 1) else "", 10)
        pdf.set_x(pdf.l_margin)
        pdf.cell(box_w, 9, f"  {label}", fill=True, new_x="LMARGIN", new_y="NEXT")
        if i < len(steps) - 1:
            pdf.set_font("Arial", "", 14)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(box_w, 5, "v", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # ── Glossary ─────────────────────────────────────────────────────────────
    pdf.chapter_title("8.  Glossary")

    terms = [
        ("Diarization",
         "The process of partitioning an audio stream into segments according to "
         "who is speaking. The name comes from 'diary' -- a record of who said what when."),
        ("Voice Activity Detection (VAD)",
         "A pre-processing step that identifies which parts of an audio file contain "
         "speech and which are silence or noise. This avoids wasting computation on "
         "non-speech frames."),
        ("Speaker Embedding",
         "A fixed-size vector of numbers that encodes the acoustic characteristics "
         "of a speaker's voice. Similar voices produce similar vectors."),
        ("Cosine Similarity",
         "A measure of how similar two vectors are, regardless of their length. "
         "A value of 1.0 means they point in the same direction (identical voices); "
         "0.0 means they are completely unrelated."),
        ("Spectrogram",
         "A 2-D visual representation of audio where the x-axis is time, the y-axis "
         "is frequency, and the brightness/colour shows the energy at each frequency "
         "at each moment. Neural networks process spectrograms like images."),
        ("ResNet (Residual Network)",
         "A deep neural network architecture that uses skip connections to allow "
         "gradients to flow easily during training. Originally designed for image "
         "classification, widely adapted for audio feature extraction."),
        ("PLDA (Probabilistic Linear Discriminant Analysis)",
         "A classical statistical model that refines similarity scores between "
         "speaker embeddings by accounting for within-speaker variability."),
        ("pydub",
         "A Python library that provides a high-level interface for audio editing: "
         "slicing, concatenating, overlaying, and exporting audio segments."),
        ("Sample Rate",
         "The number of audio samples recorded per second. 16,000 Hz (16 kHz) is "
         "standard for speech processing. Higher rates capture more detail but "
         "require more storage and computation."),
        ("HuggingFace Hub",
         "An online platform for sharing and downloading pre-trained machine learning "
         "models. Acts as a repository (like PyPI or npm) but for neural networks."),
        ("Gated Model",
         "A HuggingFace model that requires you to log in and accept terms of use "
         "before you can download it. Access is granted per-user."),
        ("Source Separation",
         "A different (harder) problem: given a mixed audio signal, recover the "
         "individual source signals (one per speaker). Unlike diarization, it "
         "produces audio where the other speaker is truly removed, not just silenced."),
    ]

    for term, definition in terms:
        pdf.set_font("Arial", "B", 10.5)
        pdf.set_text_color(30, 80, 160)
        pdf.cell(0, 7, term, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(40, 40, 40)
        pdf.set_x(pdf.l_margin + 6)
        pdf.multi_cell(0, 6, definition, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    out = Path(__file__).parent / "speaker_diarization_explainer.pdf"
    pdf.output(str(out))
    print(f"PDF written to: {out}")


if __name__ == "__main__":
    build()
