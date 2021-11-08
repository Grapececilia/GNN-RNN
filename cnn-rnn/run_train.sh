# Old dataset
# python main.py --dataset soybean --data_dir ../data/soybean_data_full.npz -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#     --mode train --length 5 -bs 64 --max_epoch 100 --test_year 2018 --model cnn_rnn \
#     -lr 5e-4 --eta_min 1e-5 --check_freq 80 --T0 50 -sche step \
#     --num_outputs 1 --num_weather_vars 6 --num_soil_vars 10 --num_management_vars 14 --num_extra_vars 4 --soil_depths 10

# New dataset
# You can change "crop_type" to the desired crop ("corn", "upland_cotton", "sorghum", "soybeans", "spring_wheat", "winter_wheat")
# Add "--share_conv_parameters" if you want each weather variable to share the same conv parameters (same with soil/progress data).
# Add "--combine_weather_and_management" if you want weather and management data to be processed together in the same CNN.
# In "data_dir", you can change "combined_dataset_weekly" to "combined_dataset_daily" to use daily data.
cd ~/Crop_Yield_Prediction/cnn-rnn

for s in 0
do
    python main.py --dataset corn_weekly --crop_type corn --model cnn_rnn --test_year 2018 \
        --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
        -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl --mode train --length 5 \
        -bs 128 --max_epoch 100 --test_year 2018 -lr 1e-4 --eta_min 1e-5 --check_freq 80 --T0 50 -sche step \
        --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
        --combine_weather_and_management --no_management --train_week_start 52 --validation_week 52 \
        --mask_prob 0.5 --mask_value zero --seed $s
done


# # 2018 corn: BEST
#  python main.py --dataset corn_weekly_no_Y_input_shuffle \
#   --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#    -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl --crop_type corn --mode train \
#    --length 5 -bs 32 --max_epoch 100 --sleep 100 --test_year 2018 -lr 5e-5 --check_freq 80 --sche cosine \
#    --eta_min 1e-6 --T0 100 --T_mult 2 --lrsteps 25 --gamma 1 --dropout 0.1 --num_weather_vars 23 \
#    --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 --aggregator_type pool \
#    --encoder_type cnn --no_management --train_week_start 52 --validation_week 52 --seed 0 --weight_decay 1e-5 --mask_prob 0.5 --mask_value zero





# # model/soybeans_weekly/soybeans_weekly_cnn_rnn_bs-128_lr-0.0005_maxepoch-100_sche-step_T0-150_testyear-2018_trainweekstart-52_len-5_seed-0_no-management/model-13

# for s in 0 1 2
# do
#     python main.py --dataset soybeans_weekly --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#         -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#         --mode train --length 5 -bs 128 --max_epoch 100 --test_year $1 --model cnn_rnn \
#         -lr 5e-4 --eta_min 1e-6 --check_freq 80 --T0 150 -sche step \
#         --crop_type soybeans --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
#         --combine_weather_and_management --no_management --train_week_start 52 --validation_week 52 \
#         --mask_prob 0.5 --mask_value zero --seed $s
# done

# ./run_train.sh 2018  [19.3]
# ./run_train.sh 2019  [19.4]


# for y in 2018 2019
# do
#     for l in 1e-5 1e-4 1e-3
#     do
#         python main.py --dataset soybeans_weekly --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#             -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#             --mode train --length 5 -bs 128 --max_epoch 100 --test_year $y --model $1 \
#             -lr $l --eta_min 1e-6 --check_freq 80 --T0 50 -sche step \
#             --crop_type soybeans --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
#             --combine_weather_and_management --no_management --train_week_start 52 --validation_week 52 \
#             --mask_prob 0.5 --mask_value zero
#     done 
# done

# Commands: 
# ./run_train.sh cnn_rnn
# ./run_train.sh rnn



# python main.py --dataset soybeans_weekly --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#     -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#     --mode train --length 5 -bs 128 --max_epoch 100 --test_year 2018 --model cnn_rnn \
#     -lr 1e-3 --eta_min 1e-5 --check_freq 80 --T0 50 -sche step \
#     --crop_type soybeans --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
#     --combine_weather_and_management --no_management --train_week_start 52 --validation_week 52 \
#     --mask_prob 0.5 --mask_value zero

# python main.py --dataset corn_weekly --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#     -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#     --mode train --length 5 -bs 128 --max_epoch 100 --test_year 2019 --model cnn_rnn \
#     -lr 1e-4 --eta_min 1e-5 --check_freq 80 --T0 50 -sche step \
#     --crop_type corn --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
#     --combine_weather_and_management --no_management

# python main.py --dataset corn_weekly --data_dir /mnt/beegfs/bulk/mirror/jyf6/datasets/crop_forecast/data/combined_dataset_weekly.npz \
#     -adj ../map/us_adj.pkl --crop_id_to_fid ../map/soybean_fid_dict.pkl \
#     --mode train --length 5 -bs 128 --max_epoch 100 --test_year 2018 --model cnn_rnn \
#     -lr 1e-4 --eta_min 1e-5 --check_freq 80 --T0 50 -sche step \
#     --crop_type corn --num_weather_vars 23 --num_management_vars 96 --num_soil_vars 20 --num_extra_vars 6 --soil_depths 6 \
#     --combine_weather_and_management --no_management