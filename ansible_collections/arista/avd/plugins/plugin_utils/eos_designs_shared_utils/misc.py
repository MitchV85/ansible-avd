from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from ansible_collections.arista.avd.plugins.filter.convert_dicts import convert_dicts
from ansible_collections.arista.avd.plugins.filter.natural_sort import natural_sort
from ansible_collections.arista.avd.plugins.plugin_utils.utils import default, get

if TYPE_CHECKING:
    from .shared_utils import SharedUtils


class MiscMixin:
    """
    Mixin Class providing a subset of SharedUtils
    Class should only be used as Mixin to the SharedUtils class
    Using type-hint on self to get proper type-hints on attributes across all Mixins.
    """

    @cached_property
    def all_fabric_devices(self: SharedUtils) -> list[str]:
        avd_switch_facts: dict = get(self.hostvars, "avd_switch_facts", required=True)
        return list(avd_switch_facts.keys())

    @cached_property
    def hostname(self: SharedUtils) -> str:
        """
        hostname set based on inventory_hostname variable
        """
        return get(self.hostvars, "inventory_hostname", required=True)

    @cached_property
    def id(self: SharedUtils) -> int | None:
        return get(self.switch_data_combined, "id")

    @cached_property
    def trunk_groups(self: SharedUtils) -> dict:
        return {
            "mlag": {"name": get(self.hostvars, "trunk_groups.mlag.name", default="MLAG")},
            "mlag_l3": {"name": get(self.hostvars, "trunk_groups.mlag_l3.name", default="LEAF_PEER_L3")},
            "uplink": {"name": get(self.hostvars, "trunk_groups.uplink.name", default="UPLINK")},
        }

    @cached_property
    def enable_trunk_groups(self: SharedUtils) -> bool:
        return get(self.hostvars, "enable_trunk_groups", default=False)

    @cached_property
    def filter_only_vlans_in_use(self: SharedUtils) -> bool:
        return get(self.switch_data_combined, "filter.only_vlans_in_use", default=False)

    @cached_property
    def filter_tags(self: SharedUtils) -> list:
        """
        Return filter.tags + group if defined
        """
        filter_tags = get(self.switch_data_combined, "filter.tags", default=["all"])
        if self.group is not None:
            filter_tags.append(self.group)
        return filter_tags

    @cached_property
    def filter_tenants(self: SharedUtils) -> list:
        return get(self.switch_data_combined, "filter.tenants", default=["all"])

    @cached_property
    def igmp_snooping_enabled(self: SharedUtils) -> bool:
        default_igmp_snooping_enabled = get(self.hostvars, "default_igmp_snooping_enabled")
        return get(self.switch_data_combined, "igmp_snooping_enabled", default=default_igmp_snooping_enabled) is True

    @cached_property
    def only_local_vlan_trunk_groups(self: SharedUtils) -> bool:
        return self.enable_trunk_groups and get(self.hostvars, "only_local_vlan_trunk_groups", default=False)

    @cached_property
    def system_mac_address(self: SharedUtils) -> str | None:
        """
        system_mac_address is inherited from
        Fabric Topology data model system_mac_address ->
            Host variable var system_mac_address ->
        """
        return default(get(self.switch_data_combined, "system_mac_address"), get(self.hostvars, "system_mac_address"))

    @cached_property
    def uplink_switches(self: SharedUtils) -> list:
        return get(self.switch_data_combined, "uplink_switches", default=[])

    @cached_property
    def virtual_router_mac_address(self: SharedUtils) -> str | None:
        return get(self.switch_data_combined, "virtual_router_mac_address")

    @cached_property
    def serial_number(self: SharedUtils) -> str | None:
        """
        serial_number is inherited from
        Fabric Topology data model serial_number ->
            Host variable var serial_number
        """
        return default(get(self.switch_data_combined, "serial_number"), get(self.hostvars, "serial_number"))

    @cached_property
    def max_parallel_uplinks(self: SharedUtils) -> int:
        """
        Exposed in avd_switch_facts
        """
        return get(self.switch_data_combined, "max_parallel_uplinks", default=1)

    @cached_property
    def max_uplink_switches(self: SharedUtils) -> int:
        """
        max_uplink_switches will default to the length of uplink_switches
        """
        return get(self.switch_data_combined, "max_uplink_switches", default=len(self.uplink_switches))

    @cached_property
    def p2p_uplinks_mtu(self: SharedUtils) -> int:
        return get(self.hostvars, "p2p_uplinks_mtu", required=True)

    @cached_property
    def evpn_short_esi_prefix(self: SharedUtils) -> str:
        return get(self.hostvars, "evpn_short_esi_prefix", required=True)

    @cached_property
    def shutdown_interfaces_towards_undeployed_peers(self: SharedUtils) -> bool:
        return get(self.hostvars, "shutdown_interfaces_towards_undeployed_peers") is True

    @cached_property
    def bfd_multihop(self: SharedUtils) -> dict | None:
        return get(self.hostvars, "bfd_multihop")

    @cached_property
    def evpn_ebgp_multihop(self: SharedUtils) -> int | None:
        return get(self.hostvars, "evpn_ebgp_multihop")

    @cached_property
    def evpn_ebgp_gateway_multihop(self: SharedUtils) -> int | None:
        return get(self.hostvars, "evpn_ebgp_gateway_multihop")

    @cached_property
    def evpn_overlay_bgp_rtc(self: SharedUtils) -> bool:
        return get(self.hostvars, "evpn_overlay_bgp_rtc") is True

    @cached_property
    def evpn_prevent_readvertise_to_server(self: SharedUtils) -> bool:
        return get(self.hostvars, "evpn_prevent_readvertise_to_server") is True

    @cached_property
    def dc_name(self: SharedUtils) -> str | None:
        return get(self.hostvars, "dc_name")

    @cached_property
    def connected_endpoints_keys(self: SharedUtils) -> list:
        """
        Return connected_endpoints_keys filtered for invalid entries and unused keys
        """
        connected_endpoints_keys = []
        # Support legacy data model by converting nested dict to list of dict
        connected_endpoints_keys = convert_dicts(get(self.hostvars, "connected_endpoints_keys", default=[]), "key")
        connected_endpoints_keys = [entry for entry in connected_endpoints_keys if entry.get("key") is not None and self.hostvars.get(entry["key"]) is not None]
        return connected_endpoints_keys

    @cached_property
    def network_services_keys(self: SharedUtils) -> list[dict]:
        """
        Return sorted network_services_keys filtered for invalid entries and unused keys
        """
        network_services_keys = get(self.hostvars, "network_services_keys", required=True)
        network_services_keys = [entry for entry in network_services_keys if entry.get("name") is not None and self.hostvars.get(entry["name"]) is not None]
        return natural_sort(network_services_keys, "name")

    @cached_property
    def port_profiles(self: SharedUtils) -> list:
        port_profiles = get(self.hostvars, "port_profiles", default=[])
        # Support legacy data model by converting nested dict to list of dict
        return convert_dicts(port_profiles, "profile")

    @cached_property
    def uplink_interface_speed(self: SharedUtils) -> str | None:
        return get(self.switch_data_combined, "uplink_interface_speed")

    @cached_property
    def uplink_bfd(self: SharedUtils) -> bool:
        return get(self.switch_data_combined, "uplink_bfd") is True

    @cached_property
    def uplink_ptp(self: SharedUtils) -> dict | None:
        return get(self.switch_data_combined, "uplink_ptp")

    @cached_property
    def uplink_macsec(self: SharedUtils) -> dict | None:
        return get(self.switch_data_combined, "uplink_macsec")

    @cached_property
    def uplink_structured_config(self: SharedUtils) -> dict | None:
        return get(self.switch_data_combined, "uplink_structured_config")

    @cached_property
    def p2p_uplinks_qos_profile(self: SharedUtils) -> str | None:
        return get(self.hostvars, "p2p_uplinks_qos_profile")

    @cached_property
    def isis_default_metric(self: SharedUtils) -> int:
        return get(self.hostvars, "isis_default_metric", default=50)

    @cached_property
    def isis_default_circuit_type(self: SharedUtils) -> str | None:
        return get(self.hostvars, "isis_default_circuit_type")

    @cached_property
    def pod_name(self: SharedUtils) -> str | None:
        return get(self.hostvars, "pod_name")
