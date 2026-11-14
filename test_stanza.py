#!/usr/bin/env python3
"""Manual Stanza demo; running this script downloads the model if needed."""


def main():
    from pathlib import Path

    import stanza
    from huggingface_hub import snapshot_download

    # Download models (one time)
    model_dir = snapshot_download("latincy/la_stanza_latincy")

    # Load pipeline
    # The published tokenizer retains its training-time CharLM path, but its
    # resources.json omits that dependency. Override it with the downloaded model.
    nlp = stanza.Pipeline(
        "la",
        dir=model_dir,
        download_method=None,
        tokenize_forward_charlm_path=str(Path(model_dir) / "la/forward_charlm/latincy.pt"),
    )

    # Annotate
    text = """Musa, mihi causas memora, quo numine laeso,
    quidve dolens, regina deum tot volvere casus
    insignem pietate virum, tot adire labores
    impulerit. Tantaene animis caelestibus irae?"""

    doc = nlp(text)
    for sent in doc.sentences:
        for word in sent.words:
            print(f"{word.text:12s} {word.upos:6s} {word.lemma:12s} {word.deprel}")


if __name__ == "__main__":
    main()
