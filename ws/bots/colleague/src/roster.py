"""One legal unique pick per draft turn; imports deliberately stay small."""
import cambc as bc
DRAFT_ORDER = (bc.ChampionDraft.VARG, bc.ChampionDraft.VENDETTA,
               bc.ChampionDraft.WILLOW, bc.ChampionDraft.RYTH,
               bc.ChampionDraft.MARCELLA, bc.ChampionDraft.TAVI,
               bc.ChampionDraft.CASSI_AND_ISSAC, bc.ChampionDraft.VESPER_VALE,
               bc.ChampionDraft.REN, bc.ChampionDraft.STELLAR,
               bc.ChampionDraft.PRISM, bc.ChampionDraft.HEART_OF_RUIN)
