from __future__ import annotations

from functools import cached_property

from ansible_collections.arista.avd.plugins.plugin_utils.errors import AristaAvdMissingVariableError
from ansible_collections.arista.avd.plugins.plugin_utils.utils import get

from .utils import UtilsMixin


class LoopbackInterfacesMixin(UtilsMixin):
    """
    Mixin Class used to generate structured config for one key.
    Class should only be used as Mixin to a AvdStructuredConfig class
    """

    @cached_property
    def loopback_interfaces(self) -> list | None:
        """
        Return structured config for loopback_interfaces
        """
        if not self.shared_utils.underlay_router:
            return None

        loopback_interfaces = []
        # Loopback 0
        loopback0 = {
            "name": "Loopback0",
            "description": self.shared_utils.interface_descriptions.overlay_loopback_interface(get(self._hostvars, "overlay_loopback_description")),
            "shutdown": False,
            "ip_address": f"{self.shared_utils.router_id}/32",
        }

        if self.shared_utils.ipv6_router_id is not None:
            loopback0["ipv6_address"] = f"{self.shared_utils.ipv6_router_id}/128"

        if self.shared_utils.underlay_ospf:
            loopback0["ospf_area"] = self.shared_utils.underlay_ospf_area

        if self.shared_utils.underlay_ldp:
            loopback0["mpls"] = {"ldp": {"interface": True}}

        if self.shared_utils.underlay_isis:
            isis_config = {"isis_enable": self.shared_utils.isis_instance_name, "isis_passive": True}
            if self.shared_utils.underlay_sr:
                isis_config["node_segment"] = {"ipv4_index": self._node_sid}
                if self.shared_utils.underlay_ipv6:
                    isis_config["node_segment"].update({"ipv6_index": self._node_sid})

            loopback0.update(isis_config)

        loopback0 = {key: value for key, value in loopback0.items() if value is not None}

        loopback_interfaces.append(loopback0)

        # VTEP loopback
        if self.shared_utils.overlay_vtep is True and self.shared_utils.vtep_loopback.lower() != "loopback0":
            vtep_loopback = {
                "name": self.shared_utils.vtep_loopback,
                "description": self.shared_utils.interface_descriptions.vtep_loopback_interface(),
                "shutdown": False,
                "ip_address": f"{self.shared_utils.vtep_ip}/32",
            }

            if self.shared_utils.network_services_l3 is True and self.shared_utils.vtep_vvtep_ip is not None:
                vtep_loopback["ip_address_secondaries"] = [self.shared_utils.vtep_vvtep_ip]

            if self.shared_utils.underlay_ospf is True:
                vtep_loopback["ospf_area"] = self.shared_utils.underlay_ospf_area

            if self.shared_utils.underlay_isis is True:
                vtep_loopback.update({"isis_enable": self.shared_utils.isis_instance_name, "isis_passive": True})

            vtep_loopback = {key: value for key, value in vtep_loopback.items() if value is not None}

            loopback_interfaces.append(vtep_loopback)

        return loopback_interfaces

    @cached_property
    def _node_sid(self):
        if self.shared_utils.id is None:
            raise AristaAvdMissingVariableError(f"'id' is not set on '{self.shared_utils.hostname}' and is required to set node SID")
        node_sid_base = int(get(self.shared_utils.switch_data_combined, "node_sid_base", 0))
        return self.shared_utils.id + node_sid_base
