from typing import Iterable

from envoy.admin.schema.site import SitePageResponse, SiteResponse
from envoy.server.model.site import Site


class SiteMapper:
    @staticmethod
    def map_to_site_response(site: Site) -> SiteResponse:
        """Maps our internal Site model to an equivalent SiteResponse"""
        return SiteResponse(
            site_id=site.site_id,
            nmi=site.nmi,
            timezone_id=site.timezone_id,
            changed_time=site.changed_time,
            lfdi=site.lfdi,
            sfdi=site.sfdi,
            device_category=site.device_category,
        )

    @staticmethod
    def map_to_response(total_count: int, limit: int, start: int, sites: Iterable[Site]) -> SitePageResponse:
        """Maps a set of sites to a single SitePageResponse"""
        return SitePageResponse(
            total_count=total_count, limit=limit, start=start, sites=[SiteMapper.map_to_site_response(s) for s in sites]
        )
