
from Dataset import AgentTimestep
import numpy as np
from pyquaternion import Quaternion
import matplotlib.pyplot as plt

nusc_ends = {'singapore-onenorth': (1500, 2000),
             'singapore-queenstown': (3200, 3500),
             'singapore-hollandvillage': (2700, 3000),
             'boston-seaport': (3000, 2200)}


class Agent:
    context_dict = None

    def __init__(self, agent_id=None):
        self.agent_id = agent_id
        self.map_name = None
        self.scene_token = None
        self.timesteps = {}           # dictionary of context-scenes, the form  {id_timestep : AgentTimeStep}.
        self.index_list = []        # list of indexes that indicate the start and end of the multiple trajectories that can be obtained
                                    # from the same agent

    def add_observation(self, t_context, t_x, t_y, t_rotation, t_speed, t_accel,
                        t_heading_rate, t_ego_pos_x, t_ego_pos_y, t_ego_rotation):

        self.timesteps[t_context] = AgentTimestep(t_x, t_y, t_rotation, t_speed, t_accel,
                                                  t_heading_rate, t_ego_pos_x, t_ego_pos_y, t_ego_rotation)

    def plotMasks(self, maps: dict, height=200, width=200):
        """
        exploratory function to plot the bitmaps of an agent's positions
        :param maps: maps dictionary
        :param height: height of the bitmap
        :param width:  width of the bitmap
        :return: None
        """
        # get map
        map = maps[self.map_name]

        # traverse agent positions
        for pos in self.abs_pos:
            x, y = pos[0], pos[1]
            patch_box = (x, y, height, width)
            patch_angle = 0  # Default orientation where North is up
            layer_names = ['drivable_area', 'walkway']
            canvas_size = (1000, 1000)

            figsize = (12, 4)
            fig, ax = map.render_map_mask(patch_box, patch_angle, layer_names, canvas_size, figsize=figsize, n_row=1)
            fig.show()

    def getMasks(self, maps: dict, timestep: AgentTimestep, path: str, name: str, height=200, width=200,
                 canvas_size=(512, 512)):
        """
        function to get the bitmaps of an agent's positions
        :param maps: maps dictionary
        :param timestep: angle of rotation of the masks
        :param path: angle of rotation of the masks
        :param name: angle of rotation of the masks
        :param height: height of the bitmap
        :param width:  width of the bitmap
        :param canvas_size:  width of the bitmap
        :return: list of bitmaps (each mask contains 2 bitmaps)
        """
        # get map
        nusc_map = maps[self.map_name]
        x, y, rot = timestep.x, timestep.y, Quaternion(timestep.rot)
        yaw = rot.yaw_pitch_roll[0] * 180 / np.pi

        # build patch
        patch_box = (x, y, height, width)
        patch_angle = 0  # Default orientation (yaw=0) where North is up
        layer_names = ['drivable_area', 'lane']
        map_mask = nusc_map.get_map_mask(patch_box, patch_angle, layer_names, canvas_size)
        return map_mask
        # for layer in layer_names:
        #     fig, ax = nusc_map.render_map_mask(patch_box, patch_angle, [layer], canvas_size, figsize=(12, 4), n_row=1)
        #     fig.savefig('/'.join([path, layer, name]), format="png", dpi=canvas_size[0] / 10)
        #     plt.close(fig)

    def get_map(self, maps: dict, name, x_start, y_start, x_offset=100, y_offset=100, dpi=25.6):
        """
        function to store map from desired coordinates
        :param maps: map dictionary that containts the name as key and map object as value
        :param name: name of the file to store the map
        :param x_start: x coordinate from which to show map
        :param y_start: y coordinate from which to show map
        :param x_offset: x offset to final, i.e x_final = x_start + x_offset
        :param y_offset: y offset to final, i.e x_final = y_start + y_offset
        :param dpi: resolution of image, example 25.6  gets an image of 256 x 256 pixels
        :return: None
        """
        nusc_map, ends = maps[self.map_name], nusc_ends[self.map_name]
        x_final = min(ends[0], x_start + x_offset)
        y_final = min(ends[1], y_start + y_offset)
        my_patch = (x_start, y_start, x_final, y_final)
        fig, ax = nusc_map.render_map_patch(my_patch, ['lane', 'lane_divider', 'road_divider', 'drivable_area'], \
                                            figsize=(10, 10), render_egoposes_range=False, render_legend=False, alpha=0.55)
        fig.savefig(name, format="png", dpi=dpi)
        plt.close(fig)

    def get_map_patch(self, x_start, y_start, x_offset=100, y_offset=100):
        ends = nusc_ends[self.map_name]
        x_final = min(ends[0], x_start + x_offset)
        y_final = min(ends[1], y_start + y_offset)
        return x_start, y_start, x_final, y_final

    # return list of unique neighbors through all the trajectory
    def get_neighbors(self, kth_traj):
        if len(self.index_list) == 0:
            return None

        start, end = self.index_list[kth_traj]
        keys = list(self.timesteps.keys())
        neighbors = {}
        pos_available = 0

        # traverse all contexts (sample_annotation)
        for key in keys[start: end]:
            context = Agent.context_dict[key]

            # traverse all neighbors and add the ones that are not yet
            for neighbor_id in context.neighbors:
                if neighbors.get(neighbor_id) is None:
                    neighbors[neighbor_id] = pos_available
                    pos_available += 1

        return neighbors

    def get_transformer_matrix(self, agents: dict, kth_traj: int, offset_origin=-1):
        neighbors_positions = self.get_neighbors(kth_traj)
        start, end = self.index_list[kth_traj]

        traj_size = end - start
        matrix = np.zeros((len(neighbors_positions), traj_size, 2))
        time_steps = list(self.timesteps.keys())

        # use a fixed origin in the agent abs positions
        if offset_origin >= 0:
            x_o, y_o = self.abs_pos[offset_origin]

        for j in range(start, end):

            # use the current abs position of the agent as origin
            if offset_origin < 0:
                x_o, y_o = self.abs_pos[j]

            context_key = time_steps[j]
            agent_neighbor_ids = Agent.context_dict[context_key]['neighbors']

            for neighbor_id in agent_neighbor_ids:
                neighbor: Agent = agents[neighbor_id]
                time_pos = neighbor.timesteps.get(context_key)
                if time_pos is not None:
                    x, y = neighbor.abs_pos[time_pos]
                    i = neighbors_positions[neighbor_id]
                    matrix[i, j, 0] = x - x_o
                    matrix[i, j, 1] = y - y_o

        return matrix

    def get_features(self, timestep_id, origin_timestep=None, use_ego=True):
        x_o, y_o, origin_rot = 0, 0, (0, 0, 0, 1)
        if origin_timestep is not None:
            if use_ego:
                x_o = origin_timestep.x
                y_o = origin_timestep.y
                origin_rot = origin_timestep.rot
            else:
                x_o = origin_timestep.x
                y_o = origin_timestep.y
                origin_rot = origin_timestep.rot

        agent_time_step = self.timesteps[timestep_id]
        x_pos = agent_time_step.x - x_o
        y_pos = agent_time_step.y - y_o
        vel = agent_time_step.speed
        acc = agent_time_step.accel
        rel_rot = Quaternion(origin_rot).inverse * Quaternion(agent_time_step.rot)
        yaw, _, _ = rel_rot.yaw_pitch_roll
        yaw = yaw  # in radians
        return x_pos, y_pos, yaw, vel, acc


