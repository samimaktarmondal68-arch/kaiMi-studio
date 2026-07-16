# KaiMi Studio — Master Specification

## Product purpose

KaiMi Studio is the desktop operating system for **KaiMi**, a curiosity-first
YouTube channel explaining the hidden reasons behind everyday human life. It
manages the channel's production work from a selected idea to a publishing
package. It does not replace the external visual-generation workflow.

## Channel direction

- **Audience promise:** answer “Why do humans do this?” in an entertaining,
  clear, and memorable way.
- **Primary topic territory:** everyday human behaviour, psychology,
  evolution, hidden origins, science, and social life.
- **Content test:** a topic should be familiar, challenge an assumption, and
  leave the viewer seeing an everyday thing differently.
- **Voice:** simple conversational English; curious, energetic, and
  factually grounded; never padded or academic for its own sake.

## Non-negotiable script rules

- A standard KaiMi script is **4,800–4,999 characters**, never 5,000 or more.
- The first 5–10 seconds must create a powerful curiosity hook.
- Every section must advance the story; no filler.
- Introduce a new question, insight, or pattern interrupt about every 20–30
  seconds.
- End with a resonant thought that encourages the viewer to comment.
- Check factual claims before treating a script as ready.

## Production pipeline

1. **Topic research** — score ideas for curiosity, CTR/thumbnail potential,
   retention, evergreen value, competition, and available evidence. Present
   the strongest candidates for a human decision.
2. **Video blueprint** — establish title options, thumbnail concept, viewer
   psychology, hook strategy, and retention plan before writing.
3. **Research and script** — create the verified narration within the character
   limit, then review its hook, clarity, retention, and factual support.
4. **Voice and transcription** — the voiceover is created in ElevenLabs and
   imported/transcribed with accurate timestamps.
5. **Scene prompts** — produce one prompt for each timestamp using the exact,
   lightweight proven layout:

   ```text
   [00:00] Image prompt...

   Narration focus: ...
   ```

6. **Visual production** — Google Flow creates visuals from the prompt file;
   the team edits in DaVinci Resolve. KaiMi Studio does not generate or store
   Google Flow images as part of this workflow.
7. **Publishing kit** — after final video import, create title options,
   thumbnail copy/concept, description, SEO tags, chapters where appropriate,
   pinned comment, and community post.

## Visual direction for prompts

Use a premium hand-drawn educational storybook look: imperfect ink outlines,
soft muted watercolor-like colour, clean compositions, and expressive but
grounded characters. Avoid 3D, chibi, glossy, or generic AI-cartoon drift.
The setting changes with the story; the illustration language stays consistent.
Do not add large style-lock paragraphs, extra headings, or other prompt
"improvements" that disrupt the established Google Flow extension workflow.

## Application scope

The first complete product release should provide:

- project creation and metadata;
- a visible, guided pipeline with per-stage status;
- editors for research, blueprint, script, transcript/timestamps, and prompt
  output;
- import locations for voiceover and final video;
- a reliable script-character counter and readiness checks;
- project asset references without pretending to generate Flow visuals;
- publishing-package generation and export;
- a clean CustomTkinter desktop interface, versioned releases, and local,
  human-readable project files.

## Future integrations

- ElevenLabs voice workflow;
- transcription/Whisper;
- Google Flow prompt generation (text only);
- asset manager and publish manager.

## Delivery standard

Work on real files in the active workspace. Verify every claimed change. Do
not present an unbuilt release as complete, do not change agreed workflow rules
without approval, and do not replace human decisions at topic and blueprint
approval points.
