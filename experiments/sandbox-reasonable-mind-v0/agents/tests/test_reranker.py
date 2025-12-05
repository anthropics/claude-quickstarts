from agents.core.retrieval_augmentation import RetrievedDocument, RetrievalMode, SimpleReranker


def test_simple_reranker_orders_by_length():
    docs = [
        RetrievedDocument(doc_id="a", content="short", score=0.9, rank=1, retrieval_method=RetrievalMode.DENSE),
        RetrievedDocument(doc_id="b", content="this is longer content", score=0.5, rank=2, retrieval_method=RetrievalMode.DENSE),
    ]

    reranker = SimpleReranker()
    reranked = reranker.rerank(docs)

    assert reranked[0].doc_id == "b"
    assert reranked[1].doc_id == "a"
