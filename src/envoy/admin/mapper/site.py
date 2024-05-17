from typing import Iterable

from envoy_schema.admin.schema.site import SiteGroup as AdminSiteGroup
from envoy_schema.admin.schema.site import SitePageResponse, SiteResponse
from envoy_schema.admin.schema.site_group import SiteGroupPageResponse, SiteGroupResponse

from envoy.server.model.site import Site, SiteGroup


class SiteMapper:
    @staticmethod
    def map_to_site_response(site: Site) -> SiteResponse:
        """Maps our internal Site model to an equivalent SiteResponse. It's expected that site has their
        groups included"""

        if site.assignments:
            site_groups = [
                AdminSiteGroup(
                    site_group_id=a.group.site_group_id, name=a.group.name, changed_time=a.group.changed_time
                )
                for a in site.assignments
                if a.group
            ]
        else:
            site_groups = []

        return SiteResponse(
            aggregator_id=site.aggregator_id,
            site_id=site.site_id,
            nmi=site.nmi,
            timezone_id=site.timezone_id,
            changed_time=site.changed_time,
            lfdi=site.lfdi,
            sfdi=site.sfdi,
            device_category=site.device_category,
            groups=site_groups,
        )

    @staticmethod
    def map_to_response(total_count: int, limit: int, start: int, sites: Iterable[Site]) -> SitePageResponse:
        """Maps a set of sites to a single SitePageResponse. It's expected that sites will have their groups included"""
        return SitePageResponse(
            total_count=total_count, limit=limit, start=start, sites=[SiteMapper.map_to_site_response(s) for s in sites]
        )


class SiteGroupMapper:
    @staticmethod
    def map_to_site_group_response(group: SiteGroup, site_count: int) -> SiteGroupResponse:
        """Maps our internal SiteGroup model to an equivalent SiteResponse"""
        return SiteGroupResponse(
            site_group_id=group.site_group_id, name=group.name, changed_time=group.changed_time, total_sites=site_count
        )

    @staticmethod
    def map_to_response(
        total_count: int, limit: int, start: int, site_groups_with_count: Iterable[tuple[SiteGroup, int]]
    ) -> SiteGroupPageResponse:
        """Maps a set of sites to a single SitePageResponse"""
        return SiteGroupPageResponse(
            total_count=total_count,
            limit=limit,
            start=start,
            groups=[SiteGroupMapper.map_to_site_group_response(g, count) for (g, count) in site_groups_with_count],
        )
