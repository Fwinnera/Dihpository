"""Patch 1.0.2 draft candidate."""
import cambc as bc
# Measured over 470 ladder games: the opponents field Vesper Vale in 71% of
# games and Heart of Ruin in 70%, where this order ranked them eighth and twelfth of
# twelve and we fielded them in 3%. Both teams can field the same champion -- Ryth is
# 75% ours and 70% theirs -- so those rates are the field's preference, not what our
# own picks left them. Willow is 97% ours against 12% theirs.
DRAFT_ORDER = (bc.ChampionDraft.MARCELLA, bc.ChampionDraft.VENDETTA, bc.ChampionDraft.HEART_OF_RUIN, bc.ChampionDraft.VARG, bc.ChampionDraft.RYTH, bc.ChampionDraft.WILLOW, bc.ChampionDraft.TAVI, bc.ChampionDraft.CASSI_AND_ISSAC, bc.ChampionDraft.REN, bc.ChampionDraft.STELLAR, bc.ChampionDraft.PRISM, bc.ChampionDraft.VESPER_VALE)
