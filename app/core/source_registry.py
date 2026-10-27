from ae_sources.reddit_albums import RedditSource
from sources.gelbooru_source import GelbooruSource
from sources.realbooru_source import RealbooruSource
from sources.hypnohub_source import HypnohubSource
from sources.soundgasm_source import SoundgasmSource
from sources.erome_source import EromeSource
from ae_sources.redgifs_niches import RedgifsSource
from sources.booru_extra_sources import Rule34Source, SafebooruSource, TbibSource, XbooruSource
from sources.e621_source import E621Source
from sources.danbooru_source import DanbooruSource
from sources.moebooru_sources import YandereSource, KonachanSource
from sources.derpibooru_source import DerpibooruSource
from sources.wallhaven_source import WallhavenSource
from sources.civitai_source import CivitaiSource
from sources.lemmy_source import LemmySource
from sources.coomer_source import CoomerSource
from sources.fapello_source import FapelloSource
from sources.kemono_source import KemonoSource
from sources.freesound_source import FreesoundSource
from sources.gallery_sites import PornPicsSource, BabehubSource
from sources.pictoa_source import PictoaSource
from sources.elitebabes_source import EliteBabesSource
from sources.porngif_source import PornGifSource
from sources.pornhub_source import PornhubImagesSource
from ae_sources.video_sites import HypnotubeSource, PmvhavenSource   # the Media Collector files + two guards

SOURCE_REGISTRY = {
    "reddit": RedditSource,
    "gelbooru": GelbooruSource,
    "realbooru": RealbooruSource,
    "hypnohub": HypnohubSource,
    "soundgasm": SoundgasmSource,
    "freesound": FreesoundSource,
    "erome": EromeSource,
    "redgifs": RedgifsSource,
    "rule34": Rule34Source,
    "safebooru": SafebooruSource,
    "tbib": TbibSource,
    "xbooru": XbooruSource,
    "e621": E621Source,
    "danbooru": DanbooruSource,
    "yandere": YandereSource,
    "konachan": KonachanSource,
    "derpibooru": DerpibooruSource,
    "wallhaven": WallhavenSource,
    "civitai": CivitaiSource,
    "lemmy": LemmySource,
    "coomer": CoomerSource,
    "fapello": FapelloSource,
    "kemono": KemonoSource,
    "pornpics": PornPicsSource,
    "babehub": BabehubSource,
    "pictoa": PictoaSource,
    "elitebabes": EliteBabesSource,
    "porngif": PornGifSource,
    "pornhub_images": PornhubImagesSource,
    "hypnotube": HypnotubeSource,
    "pmvhaven": PmvhavenSource,
}

SOURCE_TYPES = list(SOURCE_REGISTRY.keys())
