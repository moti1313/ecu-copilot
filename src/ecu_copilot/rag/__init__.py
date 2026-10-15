"""Retrieval-augmented generation over the engineering documents in docs/.

Pipeline: markdown -> section chunks (with doc id + section number as metadata)
-> local embeddings (fastembed, nothing leaves the machine) -> ChromaDB, plus a BM25
index for exact terms like "E-204" or "HB4821". Search fuses both rankings (RRF).
"""
