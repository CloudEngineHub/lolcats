
export PYTHONPATH=/home/simarora/code/lolcats/

# Save the layer-by-layer outputs
torchrun --nnodes 1 --nproc_per_node 1 /home/simarora/code/lolcats/llama_recipes/save_outputs.py \
    --model_config llama3_1_8b/distill_llama3_1_8b_lk_smd_wtk64_fd64_w01 \
    --distill_config llama3_1_8b/distill_xent0_mse1000_lr1e-2 \
    --finetune_config llama3_1_8b/finetune_lora_qkvo_alpaca_clean \
    --eval_config eval_alpaca_clean \
    --lk_zero_init \
    --verbose --seed 0 --replicate 0 \
    --eval_steps 100 --dataset_chunk_size 512 \
    --enable_fsdp --low_cpu_fsdp --fsdp_activation_checkpointing

# Launch layer-by-layer training (use 1 node so each layer can be handled by diff nodes)
torchrun --nnodes 1 --nproc_per_node 1 /home/simarora/code/lolcats/llama_recipes/train_layer_by_layer.py \
    --model_config llama3_1_8b/distill_llama3_1_8b_lk_smd_wtk64_fd64_w01 \
    --distill_config llama3_1_8b/distill_xent0_mse1000_lr1e-2 \
    --finetune_config llama3_1_8b/finetune_lora_qkvo_alpaca_clean \
    --eval_config eval_alpaca_clean \
    --lk_zero_init \
    --verbose --seed 0 --replicate 0 \
    --eval_steps 100 --dataset_chunk_size 512 \
    --enable_fsdp --low_cpu_fsdp --fsdp_activation_checkpointing

