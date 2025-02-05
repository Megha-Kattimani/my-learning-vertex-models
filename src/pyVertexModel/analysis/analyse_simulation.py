import os
import pickle

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit

from src.pyVertexModel.algorithm.vertexModel import VertexModel, logger
from src.pyVertexModel.util.utils import load_state, load_variables, save_variables


def analyse_simulation(folder):
    """
    Analyse the simulation results
    :param folder:
    :return:
    """

    # Check if the pkl file exists
    if not os.path.exists(os.path.join(folder, 'features_per_time.pkl')):
        # return None, None, None, None
        vModel = VertexModel(create_output_folder=False)

        features_per_time = []
        features_per_time_all_cells = []

        # Go through all the files in the folder
        all_files = os.listdir(folder)

        # Sort files by date
        all_files = sorted(all_files, key=lambda x: os.path.getmtime(os.path.join(folder, x)))
        for file_id, file in enumerate(all_files):
            if file.endswith('.pkl') and not file.__contains__('data_step_before_remodelling') and not file.__contains__('recoil'):
                # Load the state of the model
                load_state(vModel, os.path.join(folder, file))

                # Analyse the simulation
                all_cells, avg_cells = vModel.analyse_vertex_model()
                features_per_time_all_cells.append(all_cells)
                features_per_time.append(avg_cells)

                # # Create a temporary directory to store the images
                # temp_dir = os.path.join(folder, 'images')
                # if not os.path.exists(temp_dir):
                #     os.mkdir(temp_dir)
                # vModel.screenshot(temp_dir)

                # temp_dir = os.path.join(folder, 'images_wound_edge')
                # if not os.path.exists(temp_dir):
                #     os.mkdir(temp_dir)
                # _, debris_cells = vModel.geo.compute_wound_centre()
                # list_of_cell_distances_top = vModel.geo.compute_cell_distance_to_wound(debris_cells, location_filter=0)
                # alive_cells = [cell.ID for cell in vModel.geo.Cells if cell.AliveStatus == 1]
                # wound_edge_cells = []
                # for cell_num, cell_id in enumerate(alive_cells):
                #     if list_of_cell_distances_top[cell_num] == 1:
                #         wound_edge_cells.append(cell_id)
                # vModel.screenshot(temp_dir, wound_edge_cells)

        if not features_per_time:
            return None, None, None, None

        # Export to xlsx
        features_per_time_all_cells_df = pd.DataFrame(np.concatenate(features_per_time_all_cells),
                                                      columns=features_per_time_all_cells[0].columns)
        features_per_time_all_cells_df.sort_values(by='time', inplace=True)
        features_per_time_all_cells_df.to_excel(os.path.join(folder, 'features_per_time_all_cells.xlsx'))

        features_per_time_df = pd.DataFrame(features_per_time)
        features_per_time_df.sort_values(by='time', inplace=True)
        features_per_time_df.to_excel(os.path.join(folder, 'features_per_time.xlsx'))

        # Obtain pre-wound features
        try:
            pre_wound_features = features_per_time_df['time'][features_per_time_df['time'] < vModel.set.TInitAblation]
            pre_wound_features = features_per_time_df[features_per_time_df['time'] ==
                                                      pre_wound_features.iloc[-1]]
        except Exception as e:
            pre_wound_features = features_per_time_df.iloc[0]

        # Obtain post-wound features
        post_wound_features = features_per_time_df[features_per_time_df['time'] >= vModel.set.TInitAblation]

        if not post_wound_features.empty:
            # Reset time to ablation time.
            post_wound_features.loc[:, 'time'] = post_wound_features['time'] - vModel.set.TInitAblation

            # Compare post-wound features with pre-wound features in percentage
            for feature in post_wound_features.columns:
                if np.any(np.isnan(pre_wound_features[feature])) or np.any(np.isnan(post_wound_features[feature])):
                    continue

                if feature == 'time':
                    continue
                post_wound_features.loc[:, feature] = (post_wound_features[feature] / np.array(
                    pre_wound_features[feature])) * 100

            # Export to xlsx
            post_wound_features.to_excel(os.path.join(folder, 'post_wound_features.xlsx'))

            important_features = calculate_important_features(post_wound_features)
        else:
            important_features = {
                'max_recoiling_top': np.nan,
                'max_recoiling_time_top': np.nan,
                'min_height_change': np.nan,
                'min_height_change_time': np.nan,
            }

        # Export to xlsx
        df = pd.DataFrame([important_features])
        df.to_excel(os.path.join(folder, 'important_features.xlsx'))

        # Save dataframes to a single pkl
        with open(os.path.join(folder, 'features_per_time.pkl'), 'wb') as f:
            pickle.dump(features_per_time_df, f)
            pickle.dump(important_features, f)
            pickle.dump(post_wound_features, f)
            pickle.dump(features_per_time_all_cells_df, f)

    else:
        # Load dataframes from pkl
        with open(os.path.join(folder, 'features_per_time.pkl'), 'rb') as f:
            features_per_time_df = pickle.load(f)
            important_features = pickle.load(f)
            post_wound_features = pickle.load(f)
            features_per_time_all_cells_df = pickle.load(f)

        important_features = calculate_important_features(post_wound_features)

    # Plot wound area top evolution over time and save it to a file
    plot_feature(folder, post_wound_features, name='wound_area_top')
    plot_feature(folder, post_wound_features, name='wound_height')
    plot_feature(folder, post_wound_features, name='num_cells_wound_edge_top')

    return features_per_time_df, post_wound_features, important_features, features_per_time_all_cells_df


def plot_feature(folder, post_wound_features, name='wound_area_top'):
    """
    Plot a feature and save it to a file
    :param folder:
    :param post_wound_features:
    :param name:
    :return:
    """
    plt.figure()
    plt.plot(post_wound_features['time'], post_wound_features[name])
    plt.xlabel('Time (h)')
    plt.ylabel(name)
    # Change axis limits
    plt.xlim([0, 60])
    plt.ylim([0, 200])
    plt.savefig(os.path.join(folder, name + '.png'))
    plt.close()


def calculate_important_features(post_wound_features):
    """
    Calculate important features from the post-wound features
    :param post_wound_features:
    :return:
    """
    # Obtain important features for post-wound
    if not post_wound_features['wound_area_top'].empty and post_wound_features['time'].iloc[-1] > 4:
        important_features = {
            'max_recoiling_top': np.max(post_wound_features['wound_area_top']),
            'max_recoiling_time_top': np.array(post_wound_features['time'])[
                np.argmax(post_wound_features['wound_area_top'])],
            'min_recoiling_top': np.min(post_wound_features['wound_area_top']),
            'min_recoiling_time_top': np.array(post_wound_features['time'])[
                np.argmin(post_wound_features['wound_area_top'])],
            'min_height_change': np.min(post_wound_features['wound_height']),
            'min_height_change_time': np.array(post_wound_features['time'])[
                np.argmin(post_wound_features['wound_height'])],
            'last_area_top': post_wound_features['wound_area_top'].iloc[-1],
            'last_area_time_top': post_wound_features['time'].iloc[-1],
        }

        # Extrapolate features to a given time
        times_to_extrapolate = {3.0, 6.0, 9.0, 12.0, 15.0, 21.0, 30.0, 36.0, 45.0, 51.0, 60.0}
        columns_to_extrapolate = {'wound_area_top', 'wound_height'}  # post_wound_features.columns
        for feature in columns_to_extrapolate:
            for time in times_to_extrapolate:
                # Extrapolate results to a given time
                important_features[feature + '_extrapolated_' + str(time)] = np.interp(time,
                                                                                       post_wound_features['time'],
                                                                                       post_wound_features[feature])

        # # Get ratio from area the first time to the other times
        # for time in times_to_extrapolate:
        #     if time != 6.0:
        #         important_features['ratio_area_top_' + str(time)] = (
        #                 important_features['wound_area_top_extrapolated_' + str(time)] /
        #                 important_features['wound_area_top_extrapolated_6.0'])

    else:
        important_features = {
            'max_recoiling_top': np.nan,
            'max_recoiling_time_top': np.nan,
            'min_height_change': np.nan,
            'min_height_change_time': np.nan,
        }

    return important_features


def analyse_edge_recoil(file_name_v_model, type_of_ablation='recoil_edge_info_apical', n_ablations=2, location_filter=0, t_end=0.5):
    """
    Analyse how much an edge recoil if we ablate an edge of a cell
    :param type_of_ablation:
    :param t_end: Time to iterate after the ablation
    :param file_name_v_model: file nae of the Vertex model
    :param n_ablations: Number of ablations to perform
    :param location_filter: Location filter
    :return:
    """

    v_model = VertexModel(create_output_folder=False)
    load_state(v_model, file_name_v_model)

    # Cells to ablate
    # cell_to_ablate = np.random.choice(possible_cells_to_ablate, 1)
    cell_to_ablate = [v_model.geo.Cells[0]]

    #Pick the neighbouring cell to ablate
    neighbours = cell_to_ablate[0].compute_neighbours(location_filter)

    # Random order of neighbours
    np.random.seed(0)
    np.random.shuffle(neighbours)

    list_of_dicts_to_save = []
    for num_ablation in range(n_ablations):
        load_state(v_model, file_name_v_model)
        try:
            vars = load_variables(file_name_v_model.replace('before_ablation.pkl', type_of_ablation + '.pkl'))
            list_of_dicts_to_save_loaded = vars['recoiling_info_df_apical']

            cell_to_ablate_ID = list_of_dicts_to_save_loaded['cell_to_ablate'][num_ablation]
            neighbour_to_ablate_ID = list_of_dicts_to_save_loaded['neighbour_to_ablate'][num_ablation]
            edge_length_init = list_of_dicts_to_save_loaded['edge_length_init'][num_ablation]
            edge_length_final = list_of_dicts_to_save_loaded['edge_length_final'][num_ablation]
            if 'edge_length_final_normalized' in list_of_dicts_to_save_loaded:
                edge_length_final_normalized = list_of_dicts_to_save_loaded['edge_length_final_normalized'][
                    num_ablation]
            else:
                edge_length_final_normalized = (edge_length_final - edge_length_init) / edge_length_init

            initial_recoil = list_of_dicts_to_save_loaded['initial_recoil_in_s'][num_ablation]
            K = list_of_dicts_to_save_loaded['K'][num_ablation]
            scutoid_face = list_of_dicts_to_save_loaded['scutoid_face'][num_ablation]
            distance_to_centre = list_of_dicts_to_save_loaded['distance_to_centre'][num_ablation]
            if 'time_steps' in list_of_dicts_to_save_loaded:
                time_steps = list_of_dicts_to_save_loaded['time_steps'][num_ablation]
            else:
                time_steps = np.arange(0, len(edge_length_final)) * 6

            if edge_length_final[0] == 0:
                # Remove the first element
                edge_length_final = edge_length_final[1:]
                time_steps = time_steps[1:]
        except Exception as e:
            logger.info('Performing the analysis...' + str(e))
            # Change name of folder and create it
            if type_of_ablation == 'recoil_info_apical':
                v_model.set.OutputFolder = v_model.set.OutputFolder + '_ablation_' + str(num_ablation)
            else:
                v_model.set.OutputFolder = v_model.set.OutputFolder + '_ablation_edge_' + str(num_ablation)

            if not os.path.exists(v_model.set.OutputFolder):
                os.mkdir(v_model.set.OutputFolder)

            neighbour_to_ablate = [neighbours[num_ablation]]

            # Calculate if the cell is neighbour on both sides
            scutoid_face = None
            neighbours_other_side = []
            if location_filter == 0:
                neighbours_other_side = cell_to_ablate[0].compute_neighbours(location_filter=2)
                scutoid_face = np.nan
            elif location_filter == 2:
                neighbours_other_side = cell_to_ablate[0].compute_neighbours(location_filter=0)
                scutoid_face = np.nan

            if scutoid_face is not None:
                if neighbour_to_ablate[0] in neighbours_other_side:
                    scutoid_face = True
                else:
                    scutoid_face = False

            # Get the centre of the tissue
            centre_of_tissue = v_model.geo.compute_centre_of_tissue()
            neighbour_to_ablate_cell = [cell for cell in v_model.geo.Cells if cell.ID == neighbour_to_ablate[0]][0]
            distance_to_centre = np.mean([cell_to_ablate[0].compute_distance_to_centre(centre_of_tissue),
                                          neighbour_to_ablate_cell.compute_distance_to_centre(centre_of_tissue)])

            # Pick the neighbour and put it in the list
            cells_to_ablate = [cell_to_ablate[0].ID, neighbour_to_ablate[0]]

            # Get the edge that share both cells
            edge_length_init = v_model.geo.get_edge_length(cells_to_ablate, location_filter)

            # Ablate the edge
            v_model.set.ablation = True
            v_model.geo.cellsToAblate = cells_to_ablate
            v_model.set.TInitAblation = v_model.t
            if type_of_ablation == 'recoil_info_apical':
                v_model.geo.ablate_cells(v_model.set, v_model.t, combine_cells=False)
                v_model.geo.y_ablated = []
            elif type_of_ablation == 'recoil_edge_info_apical':
                v_model.geo.y_ablated = v_model.geo.ablate_edge(v_model.set, v_model.t, domain=location_filter,
                                                                adjacent_surface=False)

            # Relax the system
            initial_time = v_model.t
            v_model.set.tend = v_model.t + t_end
            if type_of_ablation == 'recoil_info_apical':
                v_model.set.dt = 0.005
            elif type_of_ablation == 'recoil_edge_info_apical':
                v_model.set.dt = 0.005

            v_model.set.Remodelling = False

            v_model.set.dt0 = v_model.set.dt
            if type_of_ablation == 'recoil_edge_info_apical':
                v_model.set.RemodelingFrequency = 0.05
            else:
                v_model.set.RemodelingFrequency = 100
            v_model.set.ablation = False
            v_model.set.export_images = True
            if v_model.set.export_images and not os.path.exists(v_model.set.OutputFolder + '/images'):
                os.mkdir(v_model.set.OutputFolder + '/images')
            edge_length_final_normalized = []
            edge_length_final = []
            recoil_speed = []
            time_steps = []

            # if os.path.exists(v_model.set.OutputFolder):
            #     list_of_files = os.listdir(v_model.set.OutputFolder)
            #     # Get file modification times and sort files by date
            #     files_with_dates = [(file, os.path.getmtime(os.path.join(v_model.set.OutputFolder, file))) for file in
            #                         list_of_files]
            #     files_with_dates.sort(key=lambda x: x[1])
            #     for file in files_with_dates:
            #         load_state(v_model, os.path.join(v_model.set.OutputFolder, file[0]))
            #         compute_edge_length_v_model(cells_to_ablate, edge_length_final, edge_length_final_normalized,
            #                                     edge_length_init, initial_time, location_filter, recoil_speed,
            #                                     time_steps,
            #                                     v_model)

            while v_model.t <= v_model.set.tend and not v_model.didNotConverge:
                gr = v_model.single_iteration()

                compute_edge_length_v_model(cells_to_ablate, edge_length_final, edge_length_final_normalized,
                                            edge_length_init, initial_time, location_filter, recoil_speed, time_steps,
                                            v_model)

                if np.isnan(gr):
                    break

            cell_to_ablate_ID = cell_to_ablate[0].ID
            neighbour_to_ablate_ID = neighbour_to_ablate[0]

        K, initial_recoil, error_bars = fit_ablation_equation(edge_length_final, time_steps)

        # Generate a plot with the edge length final and the fit for each ablation
        plt.figure()
        plt.plot(time_steps, edge_length_final_normalized, 'o')
        # Plot fit line of the Kelvin-Voigt model
        plt.plot(time_steps, recoil_model(np.array(time_steps), initial_recoil, K), 'r')
        plt.xlabel('Time (s)')
        plt.ylabel('Edge length final')
        plt.title('Ablation fit - ' + str(cell_to_ablate_ID) + ' ' + str(neighbour_to_ablate_ID))

        # Save plot
        if type_of_ablation == 'recoil_info_apical':
            plt.savefig(
                os.path.join(file_name_v_model.replace('before_ablation.pkl', 'ablation_fit_' + str(num_ablation) + '.png'))
            )
        elif type_of_ablation == 'recoil_edge_info_apical':
            plt.savefig(
                os.path.join(file_name_v_model.replace('before_ablation.pkl', 'ablation_edge_fit_' + str(num_ablation) + '.png'))
            )
        plt.close()

        # Save the results
        dict_to_save = {
            'cell_to_ablate': cell_to_ablate_ID,
            'neighbour_to_ablate': neighbour_to_ablate_ID,
            'edge_length_init': edge_length_init,
            'edge_length_final': edge_length_final,
            'edge_length_final_normalized': edge_length_final_normalized,
            'initial_recoil_in_s': initial_recoil,
            'K': K,
            'scutoid_face': scutoid_face,
            'location_filter': location_filter,
            'distance_to_centre': distance_to_centre,
            'time_steps': time_steps,
        }
        list_of_dicts_to_save.append(dict_to_save)

    recoiling_info_df_apical = pd.DataFrame(list_of_dicts_to_save)
    recoiling_info_df_apical.to_excel(file_name_v_model.replace('before_ablation.pkl', type_of_ablation+'.xlsx'))
    save_variables({'recoiling_info_df_apical': recoiling_info_df_apical},
                   file_name_v_model.replace('before_ablation.pkl', type_of_ablation+'.pkl'))

    return list_of_dicts_to_save


def recoil_model(x, initial_recoil, K):
    """
    Model of the recoil based on a Kelvin-Voigt model
    :param x:
    :param initial_recoil:
    :param K:
    :return:   Recoil
    """
    return (initial_recoil / K) * (1 - np.exp(-K * x))


def fit_ablation_equation(edge_length_final_normalized, time_steps):
    """
    Fit the ablation equation. Thanks to Veronika Lachina.
    :param edge_length_final_normalized:
    :param time_steps:
    :return:    K, initial_recoil
    """

    # Normalize the edge length
    edge_length_init = edge_length_final_normalized[0]
    edge_length_final_normalized = (edge_length_final_normalized - edge_length_init) / edge_length_init

    # Fit the model to the data
    [params, covariance] = curve_fit(recoil_model, time_steps, edge_length_final_normalized,
                                     p0=[0.00001, 3], bounds=(0, np.inf))

    # Get the error
    error_bars = np.sqrt(np.diag(covariance))

    initial_recoil, K = params
    return K, initial_recoil, error_bars


def compute_edge_length_v_model(cells_to_ablate, edge_length_final, edge_length_final_normalized, edge_length_init,
                                initial_time, location_filter, recoil_speed, time_steps, v_model):
    """
    Compute the edge length of the edge that share the cells_to_ablate
    :param cells_to_ablate:
    :param edge_length_final:
    :param edge_length_final_normalized:
    :param edge_length_init:
    :param initial_time:
    :param location_filter:
    :param recoil_speed:
    :param time_steps:
    :param v_model:
    :return:
    """
    if v_model.t == initial_time:
        return
    # Get the edge length
    edge_length_final.append(v_model.geo.get_edge_length(cells_to_ablate, location_filter))
    edge_length_final_normalized.append((edge_length_final[-1] - edge_length_init) / edge_length_init)
    print('Edge length final: ', edge_length_final[-1])
    # In seconds. 1 t = 1 minute = 60 seconds
    time_steps.append((v_model.t - initial_time) * 60)
    # Calculate the recoil
    recoil_speed.append(edge_length_final_normalized[-1] / time_steps[-1])
