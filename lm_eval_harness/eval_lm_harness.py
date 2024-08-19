"""
Evaluate models with lm-evaluation-harness
"""
import sys
import os
from os.path import join
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = 'true'

import argparse
import torch

# from lm_eval_harness.model_loader import load_model_from_checkpoint, load_model_from_config
from src.model.load_model_for_eval import load_model_from_checkpoint, load_model_from_config

LM_EVALUATION_HARNESS_PATH = '/juice2/scr2/mzhang/projects/lm-evaluation-harness'  # Change this to where you clone LM eval harness from


OPEN_LLM = [  # task, shots
    ('arc-challenge', 25),
    ('hellaswag', 10),
    ('truthfulqa-mc', 0),
    ('winogrande', 5),
    ('gsm8k', 5),
]
ZERO_SHOT = [
    ('lambada_openai', 0),
    ('hellaswag', 0),
    ('piqa', 0),
    ('arc-challenge', 0),
    ('arc-easy', 0),
    ('winogrande', 0),
]


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_name", type=str, default='hedgehog-eval')
    parser.add_argument("--model_type", type=str, default=None,
                        choices=['hedgehog_ckpt', 'model_config', 'huggingface'])
    parser.add_argument("--model_config", type=str, default=None)
    parser.add_argument("--cache_dir", type=str, default=None)
    
    # If model_name == 'hedghog', paths to checkpoints
    parser.add_argument("--attn_mlp_checkpoint_path", type=str, default=None)
    parser.add_argument("--finetune_checkpoint_path", type=str, default=None)
    parser.add_argument("--config_dir", type=str, default='./configs')

    parser.add_argument("--task", type=str, default=None)
    parser.add_argument("--num_shots", type=int, default=0)

    # LM Evaluation Harness args
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--max_batch_size", type=int, default=1)
    parser.add_argument("--no_cache", action='store_true', default=None)
    parser.add_argument("--limit", type=float, default=None,  # helpful for debugging
                        help="Limit the number of examples per task. "
                             "If <1, limit is a percentage of the total number of examples.")
    # Miscellaneous
    parser.add_argument("--verbose", action='store_true', default=False)
    parser.add_argument("--debug", action='store_true', default=False)
    parser.add_argument("--no_wandb", action='store_true', default=False)
    parser.add_argument("--wandb_entity", type=str, default='hazy-research')
    parser.add_argument("--replicate", type=int, default=None)
    
    args = parser.parse_args()

    args.run_name = f'd={args.task}-ns={args.num_shots}'
    if args.model_type == 'hedgehog_ckpt':
        if args.finetune_checkpoint_path is not None:
            args.run_name += f"-c={args.finetune_checkpoint_path.split('/')[-1]}"
    elif args.model_type == 'model_config':
        args.run_name += f"-c={args.model_config}"
    if args.replicate is not None:
        args.run_name += f"-r={args.replicate}"
    return args


def init_wandb(args):
    if args.no_wandb:
        wandb = None
    else:
        import wandb
        wandb.init(config={},
                   entity=args.wandb_entity,
                   name=args.run_name,
                   project=args.project_name)
    return wandb


def main():
    sys.path.append(LM_EVALUATION_HARNESS_PATH)
    from lm_eval import evaluator
    
    args = get_args()
    if args.model_type == 'hedgehog_ckpt':  # load hedgehog model
        model, model_config, tokenizer = load_model_from_checkpoint(
            attn_mlp_checkpoint_path=args.attn_mlp_checkpoint_path,
            finetune_checkpoint_path=args.finetune_checkpoint_path,
            config_dir=args.config_dir,
            print_model=args.verbose,
            debug=args.debug,
            lm_eval_model=True,
            path_to_lm_eval_harness=LM_EVALUATION_HARNESS_PATH,
        )
    elif args.model_type == 'model_config':
        model, model_config, tokenizer = load_model_from_config(
            model_config_name=args.model_config,
            config_dir=args.config_dir,
            lm_eval_model=True,
            path_to_lm_eval_harness=LM_EVALUATION_HARNESS_PATH,
        )
    elif args.model_type == 'huggingface':
        from lm_eval.models import get_model
        model = get_model('hf-causal-experimental').create_from_arg_string(
            '', {'cache_dir': args.cache_dir}
        )

    try: 
        device = model.device
    except:
        try: 
            device = model.model.device
        except:
            device = torch.device('cuda:0')

    # WandB logging
    wandb = init_wandb(args)
    if wandb is not None:
        attn_mlp_checkpoint = (args.attn_mlp_checkpoint_path.split('/')[-1] 
                               if args.attn_mlp_checkpoint_path is not None else None)
        finetune_checkpoint = (args.finetune_checkpoint_path.split('/')[-1] 
                               if args.finetune_checkpoint_path is not None else None)
        wandb.config.update({
            'model_type': args.model_type,
            'model_config': args.model_config,
            'attn_mlp_checkpoint': attn_mlp_checkpoint,
            'finetune_checkpoint': finetune_checkpoint,
            'task': args.task,
            'num_shots': args.num_shots,
            'batch_size': args.batch_size,
            'max_batch_size': args.max_batch_size,
        })

    if args.task in ['mmlu', 'mmlu_alpaca_v2']:
        from lm_eval.tasks import TASK_REGISTRY
        tasks = sorted([k for k in TASK_REGISTRY.keys() if f'{args.task}-' in k])
    else:
        tasks = [args.task]

    results = evaluator.simple_evaluate(
        model=model,  
        model_args='',  
        tasks=tasks,
        num_fewshot=args.num_shots,
        batch_size=args.batch_size,
        max_batch_size=args.max_batch_size,
        device=device,
        no_cache=args.no_cache,
        limit=args.limit,
        description_dict={},  # description_dict,
        decontamination_ngrams_path=None,  # args.decontamination_ngrams_path,
        check_integrity=None,  # args.check_integrity,
        write_out=False,  # args.write_out,
        output_base_path=None,  # args.output_base_path,
    )

    if args.task in ['mmlu', 'mmlu_alpaca_v2']:
        mmlu_accs = []
        for k, v in results['results'].items():
            if 'mmlu' in k:
                mmlu_accs.append(v['acc'])
        print(mmlu_accs)
        if len(mmlu_accs) > 0:
            results['results']['mmlu'] = {'acc': sum(mmlu_accs) / len(mmlu_accs)}
    
        print('MMLU RESULT:', results['results']['mmlu'])
    print(results)
            
    if wandb is not None:
        wandb.log(results)


if __name__ == '__main__':
    main()