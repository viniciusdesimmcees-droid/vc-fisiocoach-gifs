"""Persistência GRÁTIS e permanente do banco (histórico + fichas) num Dataset
privado do Hugging Face.

Ative criando um token de escrita e adicionando como SECRET `HF_TOKEN` no Space.
Opcional: `DATA_REPO` (ex.: "usuario/vf-tenis-data") — senão é criado
automaticamente como "<seu_usuario>/vf-tenis-data".

Sem o token, tudo continua funcionando localmente (efêmero) — esta camada é
opcional e nunca derruba o app (todas as falhas são silenciosas).
"""

from __future__ import annotations

import os
import shutil
import traceback

HF_TOKEN = os.environ.get("HF_TOKEN")
DATA_REPO = os.environ.get("DATA_REPO")
DB_FILENAME = "history.db"

_resolved_repo = None


def enabled() -> bool:
    return bool(HF_TOKEN)


def _api_and_repo():
    global _resolved_repo
    from huggingface_hub import HfApi

    api = HfApi(token=HF_TOKEN)
    repo = DATA_REPO or _resolved_repo
    if not repo:
        who = api.whoami()
        user = who.get("name") or who.get("fullname")
        repo = f"{user}/vf-tenis-data"
    _resolved_repo = repo
    return api, repo


def pull_db(db_path: str) -> None:
    """Baixa o banco do Dataset para `db_path` (chamado na inicialização)."""
    if not enabled():
        return
    try:
        from huggingface_hub import hf_hub_download

        api, repo = _api_and_repo()
        api.create_repo(repo_id=repo, repo_type="dataset", private=True, exist_ok=True)
        try:
            local = hf_hub_download(
                repo_id=repo, repo_type="dataset", filename=DB_FILENAME,
                token=HF_TOKEN, force_download=True,
            )
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            shutil.copy(local, db_path)
            print(f"[storage] histórico restaurado de {repo}")
        except Exception:
            print(f"[storage] cofre {repo} pronto (ainda sem histórico).")
    except Exception:
        traceback.print_exc()


def push_db(db_path: str) -> None:
    """Envia o banco atualizado para o Dataset (após cada gravação)."""
    if not enabled() or not os.path.exists(db_path):
        return
    try:
        api, repo = _api_and_repo()
        api.upload_file(
            path_or_fileobj=db_path, path_in_repo=DB_FILENAME,
            repo_id=repo, repo_type="dataset", token=HF_TOKEN,
            commit_message="atualiza histórico/fichas",
        )
    except Exception:
        traceback.print_exc()
