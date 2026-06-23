"""
Build a complete, simulation-ready URDF file from processed link/joint data.
Produces valid ROS 2 URDF with visual meshes, collision meshes, and
calibrated inertial properties.
"""
import os
from typing import List, Dict

from lxml import etree

from utils.logger import get_logger

log = get_logger(__name__)


class URDFGenerator:

    def generate(self,
                 links: List[Dict],
                 joints: List[Dict],
                 package_name: str,
                 output_path: str) -> str:
        """
        links:  [{name, mass, center_of_mass,
                  ixx, iyy, izz, ixy, ixz, iyz}]
        joints: [{name, type, parent, child,
                  origin_xyz, origin_rpy, axis_xyz,
                  limit_lower, limit_upper, effort, velocity}]
        Returns path to written URDF file.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        robot = etree.Element('robot', name=package_name)

        # Always include a world link (required for Gazebo fixed_joint anchor)
        etree.SubElement(robot, 'link', name='world')

        for link_data in links:
            self._add_link(robot, link_data, package_name)

        # world → first link (fixed anchor)
        if links:
            self._add_world_joint(robot, links[0]['name'])

        for jnt in joints:
            self._add_joint(robot, jnt)

        tree = etree.ElementTree(robot)
        tree.write(
            output_path,
            pretty_print=True,
            xml_declaration=True,
            encoding='UTF-8',
        )
        log.info(f"URDF written: {output_path}  ({len(links)} links, {len(joints)} joints)")
        return output_path

    # ------------------------------------------------------------------
    # Link builder
    # ------------------------------------------------------------------

    def _add_link(self, robot, d: Dict, pkg: str):
        link = etree.SubElement(robot, 'link', name=d['name'])

        # --- Visual ---
        visual = etree.SubElement(link, 'visual')
        v_geom = etree.SubElement(visual, 'geometry')
        v_mesh = etree.SubElement(v_geom, 'mesh')
        v_mesh.set('filename',
                   f'package://{pkg}/meshes/visual/{d["name"]}.dae')
        v_mesh.set('scale', '1 1 1')

        # --- Collision ---
        col = etree.SubElement(link, 'collision')
        c_geom = etree.SubElement(col, 'geometry')
        c_mesh = etree.SubElement(c_geom, 'mesh')
        c_mesh.set('filename',
                   f'package://{pkg}/meshes/collision/{d["name"]}.stl')
        c_mesh.set('scale', '1 1 1')

        # --- Inertial ---
        inertial = etree.SubElement(link, 'inertial')

        com = d.get('center_of_mass', (0.0, 0.0, 0.0))
        origin = etree.SubElement(inertial, 'origin')
        origin.set('xyz', f'{com[0]:.6f} {com[1]:.6f} {com[2]:.6f}')
        origin.set('rpy', '0 0 0')

        mass_el = etree.SubElement(inertial, 'mass')
        mass_el.set('value', f'{d.get("mass", 1.0):.6f}')

        inertia_el = etree.SubElement(inertial, 'inertia')
        inertia_el.set('ixx', f'{d.get("ixx", 0.01):.8f}')
        inertia_el.set('iyy', f'{d.get("iyy", 0.01):.8f}')
        inertia_el.set('izz', f'{d.get("izz", 0.01):.8f}')
        inertia_el.set('ixy', f'{d.get("ixy", 0.0):.8f}')
        inertia_el.set('ixz', f'{d.get("ixz", 0.0):.8f}')
        inertia_el.set('iyz', f'{d.get("iyz", 0.0):.8f}')

    # ------------------------------------------------------------------
    # Joint builders
    # ------------------------------------------------------------------

    def _add_world_joint(self, robot, first_link_name: str):
        j = etree.SubElement(robot, 'joint',
                             name='world_to_base', type='fixed')
        etree.SubElement(j, 'parent', link='world')
        etree.SubElement(j, 'child', link=first_link_name)
        origin = etree.SubElement(j, 'origin')
        origin.set('xyz', '0 0 0')
        origin.set('rpy', '0 0 0')

    def _add_joint(self, robot, d: Dict):
        jtype = d.get('type', 'fixed')
        joint = etree.SubElement(robot, 'joint',
                                 name=d['name'],
                                 type=jtype)

        etree.SubElement(joint, 'parent', link=d['parent'])
        etree.SubElement(joint, 'child',  link=d['child'])

        xyz = d.get('origin_xyz', (0, 0, 0))
        rpy = d.get('origin_rpy', (0, 0, 0))
        origin = etree.SubElement(joint, 'origin')
        origin.set('xyz', f'{xyz[0]:.6f} {xyz[1]:.6f} {xyz[2]:.6f}')
        origin.set('rpy', f'{rpy[0]:.6f} {rpy[1]:.6f} {rpy[2]:.6f}')

        if jtype in ('revolute', 'prismatic', 'continuous'):
            ax = d.get('axis_xyz', (0, 0, 1))
            axis_el = etree.SubElement(joint, 'axis')
            axis_el.set('xyz', f'{ax[0]:.6f} {ax[1]:.6f} {ax[2]:.6f}')

            if jtype in ('revolute', 'prismatic'):
                limit = etree.SubElement(joint, 'limit')
                limit.set('lower',    str(d.get('limit_lower', -3.14159)))
                limit.set('upper',    str(d.get('limit_upper',  3.14159)))
                limit.set('effort',   str(d.get('effort',   150.0)))
                limit.set('velocity', str(d.get('velocity', 3.14)))

            dynamics = etree.SubElement(joint, 'dynamics')
            dynamics.set('damping',  '0.5')
            dynamics.set('friction', '0.1')
