from __future__ import annotations

import re
from functools import cached_property
from typing import TYPE_CHECKING

from ansible_collections.arista.avd.plugins.filter.convert_dicts import convert_dicts
from ansible_collections.arista.avd.plugins.filter.list_compress import list_compress
from ansible_collections.arista.avd.plugins.filter.natural_sort import natural_sort
from ansible_collections.arista.avd.plugins.filter.range_expand import range_expand
from ansible_collections.arista.avd.plugins.plugin_utils.utils import get

if TYPE_CHECKING:
    from .eos_designs_facts import EosDesignsFacts


class VlansMixin:
    """
    Mixin Class used to generate some of the EosDesignsFacts.
    Class should only be used as Mixin to the EosDesignsFacts class
    Using type-hint on self to get proper type-hints on attributes across all Mixins.
    """

    @cached_property
    def vlans(self: EosDesignsFacts) -> str:
        """
        Exposed in avd_switch_facts

        Return the compressed list of vlans to be defined on this switch

        Ex. "1-100, 201-202"

        This excludes the optional "uplink_native_vlan" if that vlan is not used for anything else.
        This is to ensure that native vlan is not necessarily permitted on the uplink trunk.
        """
        return list_compress(self._vlans)

    def _parse_adapter_settings(self: EosDesignsFacts, adapter_settings: dict) -> tuple[set, set]:
        """
        Parse the given adapter_settings and return relevant vlans and trunk_groups
        """
        vlans = set()
        trunk_groups = set(adapter_settings.get("trunk_groups", []))
        if "vlans" in adapter_settings and adapter_settings["vlans"] not in ["all", "", None]:
            vlans.update(map(int, range_expand(str(adapter_settings["vlans"]))))
        elif "trunk" in adapter_settings.get("mode", "") and not trunk_groups:
            # No vlans or trunk_groups defined, but this is a trunk, so default is all vlans allowed
            # No need to check further, since the list is now containing all vlans.
            return set(range(1, 4094)), trunk_groups
        else:
            # No vlans or mode defined so this is an access port with only vlan 1 allowed
            vlans.add(1)

        if "native_vlan" in adapter_settings:
            vlans.add(int(adapter_settings["native_vlan"]))

        for subinterface in get(adapter_settings, "port_channel.subinterfaces", default=[]):
            if "vlan_id" in subinterface:
                vlans.add(int(subinterface["vlan_id"]))
            elif "number" in subinterface:
                vlans.add(int(subinterface["number"]))

        return vlans, trunk_groups

    @cached_property
    def _local_endpoint_vlans_and_trunk_groups(self: EosDesignsFacts) -> tuple[set, set]:
        """
        Return list of vlans and list of trunk groups used by connected_endpoints on this switch
        """
        if not (self.shared_utils.any_network_services and self.shared_utils.connected_endpoints):
            return set(), set()

        vlans = set()
        trunk_groups = set()

        for connected_endpoints_key in self.shared_utils.connected_endpoints_keys:
            connected_endpoints = convert_dicts(get(self._hostvars, connected_endpoints_key["key"], default=[]), "name")
            for connected_endpoint in connected_endpoints:
                for adapter in connected_endpoint.get("adapters", []):
                    adapter_settings = self.shared_utils.get_merged_adapter_settings(adapter)
                    if self.shared_utils.hostname not in adapter_settings.get("switches", []):
                        # This switch is not connected to this endpoint. Skipping.
                        continue

                    adapter_vlans, adapter_trunk_groups = self._parse_adapter_settings(adapter_settings)
                    vlans.update(adapter_vlans)
                    trunk_groups.update(adapter_trunk_groups)
                    if len(vlans) >= 4094:
                        # No need to check further, since the set is now containing all vlans.
                        # The trunk group list may not be complete, but it will not matter, since we will
                        # configure all vlans anyway.
                        return vlans, trunk_groups

        network_ports = get(self._hostvars, "network_ports", default=[])
        for network_port_item in network_ports:
            for switch_regex in network_port_item.get("switches", []):
                # The match test is built on Python re.match which tests from the beginning of the string #}
                # Since the user would not expect "DC1-LEAF1" to also match "DC-LEAF11" we will force ^ and $ around the regex
                switch_regex = rf"^{switch_regex}$"
                if not re.match(switch_regex, self.shared_utils.hostname):
                    # Skip entry if no match
                    continue

                adapter_settings = self.shared_utils.get_merged_adapter_settings(network_port_item)
                adapter_vlans, adapter_trunk_groups = self._parse_adapter_settings(adapter_settings)
                vlans.update(adapter_vlans)
                trunk_groups.update(adapter_trunk_groups)
                if len(vlans) >= 4094:
                    # No need to check further, since the list is now containing all vlans.
                    # The trunk group list may not be complete, but it will not matter, since we will
                    # configure all vlans anyway.
                    return vlans, trunk_groups

        return vlans, trunk_groups

    @cached_property
    def _downstream_switch_endpoint_vlans_and_trunk_groups(self: EosDesignsFacts) -> tuple[set, set]:
        """
        Return set of vlans and set of trunk groups used by downstream switches.
        Traverse any downstream L2 switches so ensure we can provide connectivity to any vlans / trunk groups used by them.
        """
        if not self.shared_utils.any_network_services:
            return set(), set()

        vlans = set()
        trunk_groups = set()
        for fabric_switch in self.shared_utils.all_fabric_devices:
            fabric_switch_facts: EosDesignsFacts = self.shared_utils.get_peer_facts(fabric_switch, required=True)
            if fabric_switch_facts.shared_utils.uplink_type == "port-channel" and self.shared_utils.hostname in fabric_switch_facts.uplink_peers:
                fabric_switch_endpoint_vlans, fabric_switch_endpoint_trunk_groups = fabric_switch_facts._endpoint_vlans_and_trunk_groups
                vlans.update(fabric_switch_endpoint_vlans)
                trunk_groups.update(fabric_switch_endpoint_trunk_groups)

        return vlans, trunk_groups

    @cached_property
    def _mlag_peer_endpoint_vlans_and_trunk_groups(self: EosDesignsFacts) -> tuple[set, set]:
        """
        Return set of vlans and set of trunk groups used by connected_endpoints on the MLAG peer.
        This could differ from local vlans and trunk groups if a connected endpoint is only connected to one leaf.
        """
        if not self.shared_utils.mlag:
            return set(), set()

        mlag_peer_facts: EosDesignsFacts = self.shared_utils.mlag_peer_facts

        return mlag_peer_facts._endpoint_vlans_and_trunk_groups

    @cached_property
    def _endpoint_vlans_and_trunk_groups(self: EosDesignsFacts) -> tuple[set, set]:
        """
        Return set of vlans and set of trunk groups used by connected_endpoints on this switch,
        downstream switches but NOT mlag peer (since we would have circular references then).
        """
        local_endpoint_vlans, local_endpoint_trunk_groups = self._local_endpoint_vlans_and_trunk_groups
        downstream_switch_endpoint_vlans, downstream_switch_endpoint_trunk_groups = self._downstream_switch_endpoint_vlans_and_trunk_groups
        return local_endpoint_vlans.union(downstream_switch_endpoint_vlans), local_endpoint_trunk_groups.union(downstream_switch_endpoint_trunk_groups)

    @cached_property
    def _endpoint_vlans(self: EosDesignsFacts) -> set[int]:
        """
        Return set of vlans in use by endpoints connected to this switch, downstream switches or MLAG peer.
        Ex: {1, 20, 21, 22, 23} or set()
        """
        if not self.shared_utils.filter_only_vlans_in_use:
            return set()

        endpoint_vlans, endpoint_trunk_groups = self._endpoint_vlans_and_trunk_groups
        if not self.shared_utils.mlag:
            return endpoint_vlans

        mlag_endpoint_vlans, mlag_endpoint_trunk_groups = self._mlag_peer_endpoint_vlans_and_trunk_groups
        return endpoint_vlans.union(mlag_endpoint_vlans)

    @cached_property
    def endpoint_vlans(self: EosDesignsFacts) -> str | None:
        """
        Return compressed list of vlans in use by endpoints connected to this switch or MLAG peer.
        Ex: "1,20-30" or ""
        """
        if self.shared_utils.filter_only_vlans_in_use:
            return list_compress(list(self._endpoint_vlans))

        return None

    @cached_property
    def _endpoint_trunk_groups(self: EosDesignsFacts) -> set[str]:
        """
        Return set of trunk_groups in use by endpoints connected to this switch, downstream switches or MLAG peer.
        """
        if not self.shared_utils.filter_only_vlans_in_use:
            return set()

        endpoint_vlans, endpoint_trunk_groups = self._endpoint_vlans_and_trunk_groups
        if not self.shared_utils.mlag:
            return endpoint_trunk_groups

        mlag_endpoint_vlans, mlag_endpoint_trunk_groups = self._mlag_peer_endpoint_vlans_and_trunk_groups
        return endpoint_trunk_groups.union(mlag_endpoint_trunk_groups)

    @cached_property
    def local_endpoint_trunk_groups(self: EosDesignsFacts) -> list[str]:
        """
        Return list of trunk_groups in use by endpoints connected to this switch only.
        Used for only applying the trunk groups in config that are relevant on this device
        This is a subset of endpoint_trunk_groups which is used for filtering.
        """
        if self.shared_utils.only_local_vlan_trunk_groups:
            local_endpoint_vlans, local_endpoint_trunk_groups = self._local_endpoint_vlans_and_trunk_groups
            return list(local_endpoint_trunk_groups)

        return []

    @cached_property
    def endpoint_trunk_groups(self: EosDesignsFacts) -> list[str]:
        """
        Return list of trunk_groups in use by endpoints connected to this switch, downstream switches or MLAG peer.
        Used for filtering which vlans we configure on the device. This is a superset of local_endpoint_trunk_groups.
        """
        return list(self._endpoint_trunk_groups)

    @cached_property
    def _vlans(self: EosDesignsFacts) -> list[int]:
        """
        Return list of vlans after filtering network services.
        The filter is based on filter.tenants, filter.tags and filter.only_vlans_in_use

        Ex. [1, 2, 3 ,4 ,201, 3021]
        """
        if self.shared_utils.any_network_services:
            vlans = []
            match_tags = self.shared_utils.filter_tags

            if self.shared_utils.filter_only_vlans_in_use:
                # Only include the vlans that are used by connected endpoints
                endpoint_trunk_groups = self._endpoint_trunk_groups
                endpoint_vlans = self._endpoint_vlans

            for network_services_key in self.shared_utils.network_services_keys:
                tenants = get(self._hostvars, network_services_key["name"])
                # Support legacy data model by converting nested dict to list of dict
                tenants = convert_dicts(tenants, "name")
                for tenant in natural_sort(tenants, "name"):
                    if not set(self.shared_utils.filter_tenants).intersection([tenant["name"], "all"]):
                        # Not matching tenant filters. Skipping this tenant.
                        continue

                    vrfs = tenant.get("vrfs", [])
                    # Support legacy data model by converting nested dict to list of dict
                    vrfs = convert_dicts(vrfs, "name")
                    for vrf in natural_sort(vrfs, "name"):
                        svis = vrf.get("svis", [])
                        # Support legacy data model by converting nested dict to list of dict
                        svis = convert_dicts(svis, "id")
                        for svi in natural_sort(svis, "id"):
                            svi_tags = svi.get("tags", ["all"])
                            if "all" in match_tags or set(svi_tags).intersection(match_tags):
                                if self.shared_utils.filter_only_vlans_in_use:
                                    # Check if vlan is in use
                                    if int(svi["id"]) in endpoint_vlans:
                                        vlans.append(int(svi["id"]))
                                        continue
                                    # Check if vlan has a trunk group defined which is in use
                                    if (
                                        self.shared_utils.enable_trunk_groups
                                        and svi.get("trunk_groups")
                                        and endpoint_trunk_groups.intersection(svi["trunk_groups"])
                                    ):
                                        vlans.append(int(svi["id"]))
                                        continue
                                    # Skip since the vlan is not in use
                                    continue
                                vlans.append(int(svi["id"]))

                    l2vlans = tenant.get("l2vlans", [])
                    # Support legacy data model by converting nested dict to list of dict
                    l2vlans = convert_dicts(l2vlans, "id")

                    for l2vlan in natural_sort(l2vlans, "id"):
                        l2vlan_tags = l2vlan.get("tags", ["all"])
                        if "all" in match_tags or set(l2vlan_tags).intersection(match_tags):
                            if self.shared_utils.filter_only_vlans_in_use:
                                # Check if vlan is in use
                                if int(l2vlan["id"]) in endpoint_vlans:
                                    vlans.append(int(l2vlan["id"]))
                                    continue
                                # Check if vlan has a trunk group defined which is in use
                                if (
                                    self.shared_utils.enable_trunk_groups
                                    and l2vlan.get("trunk_groups")
                                    and endpoint_trunk_groups.intersection(l2vlan["trunk_groups"])
                                ):
                                    vlans.append(int(l2vlan["id"]))
                                    continue
                                # Skip since the vlan is not in use
                                continue
                            vlans.append(int(l2vlan["id"]))
            return vlans
        return []
