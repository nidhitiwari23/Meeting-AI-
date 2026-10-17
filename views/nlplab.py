"""NLP Lab: see (and evaluate) how classical NLP, the confidence gateway, and retrieval actually behave."""
from __future__ import annotations

from collections import Counter
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import db, gateway, nlp, rag
from ui import charts, components as C


def _pipeline_diagram() -> None:
    nodes = [("mic", "Speech-to-text", "Whisper"), ("psychology_alt", "Classical NLP", "rules · TF-IDF · Naive Bayes"),
             ("shield", "Confidence gateway", "thresholds + evidence"), ("auto_awesome", "LLM fallback", "only if uncertain"),
             ("fact_check", "Validation", "quotes · owners · dates")]
    cells = []
    for i, (ic, t, s) in enumerate(nodes):
        cells.append(f'<div class="mx-card" style="flex:1;min-width:150px;text-align:center;padding:14px 10px"><div class="mx-logo" style="margin:0 auto 8px;width:38px;height:38px">{C.ico(ic, 20)}</div>'
                     f'<b>{t}</b><div class="mx-muted">{s}</div></div>')
        if i < len(nodes) - 1:
            cells.append(f'<div style="align-self:center;color:#8b5cf6">{C.ico("arrow_forward", 22)}</div>')
    C.md('<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:stretch">' + "".join(cells) + "</div>")


def render() -> None:
    C.page_header("NLP Lab", "Transparency for the NLP behind MeetingAI: try it live, see the metrics, and tune the confidence gateway.", "science")
    _pipeline_diagram()
    th = db.get_thresholds()
    tab_live, tab_eval, tab_gate, tab_vec = st.tabs(["  Try it live  ", "  Classifier evaluation  ", "  Gateway statistics  ", "  Semantic search  "])

    # --------------------------------------------------------------------- live
    with tab_live:
        sample = ("Priya: I will send the project report by Monday.\nAnita: Can you review the draft, Rahul?\n"
                  "Karan: Maybe we should consider hiring another developer.\nAnita: We decided to launch on the fifteenth.\n"
                  "Rahul: Let's review the prototype next Friday at 3 PM.")
        txt = st.text_area("Type or paste a few lines (one speaker per line, 'Name: sentence')", sample, height=150, key="lab_txt")
        base = st.date_input("Meeting date (used to resolve words like “Monday”)", value=date.today(), key="lab_base")
        if st.button("Analyse", type="primary", key="lab_go"):
            from core import parsing

            segs = parsing.parse_plain(txt)
            sents = nlp.build_sentences(segs)
            people = nlp.find_people(segs)
            cands = {c.sentence.idx: c for c in nlp.candidates_from(sents, base, people, min_conf=0.0)}
            rows = []
            for s in sents:
                c = cands.get(s.idx)
                if not c:
                    continue
                d = gateway.evaluate(c, th)
                ev = nlp.extract_event(s, base, False)
                rows.append({"Sentence": s.raw, "Speaker": s.speaker, "Predicted": c.cls.label, "Action": c.cls.probs.get("action", 0),
                             "Decision": c.cls.probs.get("decision", 0), "Question": c.cls.probs.get("question", 0),
                             "Discussion": c.cls.probs.get("discussion", 0), "Hedged": c.cls.rules.hedged,
                             "Owner": (c.owner.name or "Unassigned") if c.owner else "—", "Owner conf.": c.owner.confidence if c.owner else None,
                             "Deadline": (c.deadline.iso or c.deadline.phrase or "Not specified") if c.deadline else "—",
                             "Event": f"{ev['title']} · {ev['date']} {ev['time'] or ''}" if ev else "",
                             "Gateway": "ACCEPT" if d.accept else "→ LLM", "Reason": d.reason_code, "Explanation": d.message})
            if not rows:
                st.info("No sentence looked like a task or decision.")
            else:
                df = pd.DataFrame(rows)
                st.dataframe(df, hide_index=True, use_container_width=True, column_config={
                    k: st.column_config.ProgressColumn(k, min_value=0, max_value=1, format="%.2f") for k in ("Action", "Decision", "Question", "Discussion", "Owner conf.")})
                st.caption("Action/Decision/Question/Discussion are the fused scores (50% Naive Bayes, 50% rule cues). "
                           f"A task or decision is accepted when its score ≥ {th['cls_threshold']:.2f} with a margin ≥ {th['cls_margin']:.2f} "
                           f"and owner confidence ≥ {th['owner_threshold']:.2f}.")

    # --------------------------------------------------------------------- evaluation
    with tab_eval:
        ev = nlp.evaluate_classifier()
        C.md(f'<div class="mx-card"><h4>Held-out evaluation</h4><div class="mx-sub">The classical model is trained on <b>{ev["n_train"]}</b> template-generated seed sentences '
             f'and evaluated on <b>{ev["n_test"]}</b> hand-written sentences it has never seen. Because both sets were written by the project authors the numbers are '
             'optimistic - they show the pipeline works, not real-world accuracy. The confidence gateway exists precisely because a small model needs a safety net.</div></div>')
        names = [k for k in ev if isinstance(ev[k], dict) and "macro_f1" in ev[k]]
        short = {"Rules only": "Rules", "TF-IDF + Naive Bayes": "Naive Bayes", "TF-IDF + Logistic Regression": "Logistic Reg.",
                 "Fused (rules + NB) - used by MeetingAI": "Fused (in use)"}
        df = pd.DataFrame([{"Model": short.get(n, n), "Accuracy": ev[n]["accuracy"], "Macro-F1": ev[n]["macro_f1"]} for n in names])
        fig = go.Figure()
        fig.add_bar(x=df["Model"], y=df["Accuracy"], name="Accuracy", marker_color="#8B5CF6")
        fig.add_bar(x=df["Model"], y=df["Macro-F1"], name="Macro-F1", marker_color="#3B82F6")
        fig.update_layout(barmode="group", bargap=0.35, yaxis=dict(range=[0, 1.02]))
        st.plotly_chart(charts.style(fig, 300), use_container_width=True, config={"displayModeBar": False})
        a, b = st.columns([1, 1])
        with a:
            C.section("Per-class report (fused model)", "table_chart")
            rep = pd.DataFrame(ev["report"]).T.loc[ev["labels"], ["precision", "recall", "f1-score", "support"]]
            st.dataframe(rep.style.format({"precision": "{:.2f}", "recall": "{:.2f}", "f1-score": "{:.2f}", "support": "{:.0f}"}), use_container_width=True)
        with b:
            C.section("Confusion matrix", "grid_on")
            z = ev["confusion"]
            fig = go.Figure(go.Heatmap(z=z, x=ev["labels"], y=ev["labels"], colorscale=[[0, "#0f1840"], [1, "#8B5CF6"]], showscale=False,
                                       text=z, texttemplate="%{text}", hovertemplate="true %{y} → predicted %{x}: %{z}<extra></extra>"))
            fig.update_yaxes(autorange="reversed", title="true")
            fig.update_xaxes(title="predicted")
            st.plotly_chart(charts.style(fig, 300), use_container_width=True, config={"displayModeBar": False})
        with st.expander("Every test sentence"):
            rows = pd.DataFrame(ev["rows"])
            rows["correct"] = rows["gold"] == rows["pred"]
            st.dataframe(rows, hide_index=True, use_container_width=True)

        C.section("Threshold simulator", "tune")
        st.caption("What happens if the gateway threshold changes? Higher thresholds trust the classical model less: precision rises, but more items go to the LLM.")
        res_rows = ev["rows"]
        pts = []
        for t in [x / 100 for x in range(30, 100, 5)]:
            acc = [r for r in res_rows if r["confidence"] >= t]
            prec = sum(r["gold"] == r["pred"] for r in acc) / len(acc) if acc else None
            pts.append({"threshold": t, "precision of accepted": prec, "fallback rate": 1 - len(acc) / len(res_rows)})
        pdf = pd.DataFrame(pts)
        fig = go.Figure()
        fig.add_scatter(x=pdf["threshold"], y=pdf["precision of accepted"], name="Precision of accepted items", mode="lines+markers", line=dict(color="#34D399", width=2))
        fig.add_scatter(x=pdf["threshold"], y=pdf["fallback rate"], name="Share sent to the LLM", mode="lines+markers", line=dict(color="#8B5CF6", width=2))
        fig.add_vline(x=th["cls_threshold"], line=dict(color="#FBBF24", dash="dash"), annotation_text="current", annotation_font_color="#FBBF24")
        fig.update_yaxes(range=[0, 1.05], tickformat=".0%")
        fig.update_xaxes(title="classification threshold")
        st.plotly_chart(charts.style(fig, 320), use_container_width=True, config={"displayModeBar": False})

    # --------------------------------------------------------------------- gateway statistics
    with tab_gate:
        log = db.query("SELECT * FROM analysis_log")
        if not log:
            C.empty_state("shield", "No gateway decisions yet", "Analyse a meeting to see how many items were trusted, escalated or left for review.")
        else:
            tot = len(log)
            cnt = Counter(r["decision"] for r in log)
            C.metric_row([("Decisions logged", tot, "fact_check", "", ""), ("Trusted (classical)", cnt.get("accepted", 0), "verified", f"{100 * cnt.get('accepted', 0) / tot:.0f}%", "good"),
                          ("Sent to LLM", cnt.get("fallback", 0), "auto_awesome", f"{100 * cnt.get('fallback', 0) / tot:.0f}%", ""),
                          ("Human review", cnt.get("review", 0), "rule", f"{100 * cnt.get('review', 0) / tot:.0f}%", "warn"),
                          ("Rejected", cnt.get("rejected", 0), "block", "", "")])
            reasons = Counter(r["reason_code"] for r in log)
            df = pd.DataFrame(sorted(reasons.items(), key=lambda x: -x[1]), columns=["Reason", "Count"])
            df["Meaning"] = df["Reason"].map(lambda x: gateway.REASONS.get(x, ""))
            a, b = st.columns([1, 1.4])
            with a:
                fig = go.Figure(go.Bar(x=df["Count"], y=df["Reason"], orientation="h", marker_color="#8B5CF6", hovertemplate="%{y}: %{x}<extra></extra>"))
                fig.update_yaxes(autorange="reversed")
                fig.update_layout(bargap=0.4)
                st.plotly_chart(charts.style(fig, 320), use_container_width=True, config={"displayModeBar": False})
            with b:
                st.dataframe(df, hide_index=True, use_container_width=True, height=320)
            confs = [r["classical_conf"] for r in log if r["classical_conf"] is not None]
            if confs:
                C.section("Confidence distribution of candidates", "bar_chart")
                fig = go.Figure(go.Histogram(x=confs, nbinsx=20, marker_color="#3B82F6"))
                fig.add_vline(x=th["cls_threshold"], line=dict(color="#FBBF24", dash="dash"), annotation_text="threshold", annotation_font_color="#FBBF24")
                fig.update_xaxes(range=[0, 1], title="classical confidence")
                st.plotly_chart(charts.style(fig, 260), use_container_width=True, config={"displayModeBar": False})

    # --------------------------------------------------------------------- vectors
    with tab_vec:
        try:
            emb = rag.get_embedder()
            C.md(f'<div class="mx-card"><h4>Semantic index (ChromaDB)</h4><div class="mx-sub">Embedding model: <b>{emb.label}</b><br>'
                 f'Vectors stored: <b>{rag.index_count()}</b> (transcript chunks + tasks + decisions)<br>Minimum similarity to count as relevant: <b>{rag.min_similarity():.2f}</b></div></div>')
            st.caption("Type two sentences to see how close they are in meaning (cosine similarity, 1.0 = identical).")
            c1, c2 = st.columns(2)
            s1 = c1.text_input("Sentence A", "Testing took longer than expected so we missed the milestone", key="lab_a")
            s2 = c2.text_input("Sentence B", "What problems delayed the project?", key="lab_b")
            if s1 and s2:
                import numpy as np

                va = np.array(emb.embed([s1])[0]); vb = np.array(emb.embed([s2], query=True)[0])
                sim = float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb)))
                C.md(f'<div class="mx-card"><div class="mx-row" style="justify-content:space-between"><b>Similarity</b><b>{sim:.2f}</b></div>'
                     f'<div class="mx-bar"><i style="width:{max(0, min(1, sim)) * 100}%"></i></div>'
                     f'<div class="mx-muted" style="margin-top:6px">{"Related in meaning" if sim >= rag.min_similarity() else "Not related enough to count as a match"} - '
                     'even though the two sentences share almost no words. A keyword search would miss this.</div></div>')
            if st.button("Rebuild the whole index from the database", key="lab_rebuild"):
                with st.spinner("Re-embedding everything…"):
                    n = rag.rebuild_all()
                st.success(f"Rebuilt {n} vectors.")
        except Exception as e:  # noqa: BLE001
            st.error(f"The embedding model could not start: {e}")
