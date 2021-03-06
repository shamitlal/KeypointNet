import os
import sys
import time
from tqdm import tqdm
import torch
import torch.nn as nn
import numpy as np

from utils.tools import *

class Evaluator:
    def __init__(self, cfg, **kwargs):
        for key in kwargs:
            setattr(self, key, kwargs[key])
            
        self.model = self.trainer_config['model']
        self.criterion = self.trainer_config['criterion']
        self.test_data = self.trainer_config['test_data']
        self.metric = self.trainer_config['metric']
        self.geo_dists = self.trainer_config['geo_dists']
        
        self.max_epoch = cfg.max_epoch
        self.cfg = cfg

        self.ckpt_path = 'pck_best.pth'
        self.fout = open("test_result.txt", "a")

    def run(self):
        self.model.load_state_dict(torch.load(self.ckpt_path))
        tic = time.time()
        self.evaluate()
        toc = time.time()
        self.logger.info("Evaluation time is {}s".format(toc - tic))
        self.fout.close()

    def evaluate(self):
        self.model.eval()
        self.logger.info("\n-------------------Testing model----------------------")
        cnt = 0
        results_list = []
        loss_avg = 0.
        for batch_data in tqdm(self.test_data):
            with torch.no_grad():
                logits = self.model(batch_data)
            pred_index = torch.argmax(logits, dim=1)
            pcds, kp_indexs, mesh_names = batch_data
            
            loss = []
            best_kp_indexes = []
            # import pdb; pdb.set_trace()
            for b, kp_index in enumerate(kp_indexs):
                loss_rot = []
                for rot_kp_index in kp_index:
                    loss_rot.append(self.criterion((logits[b][None], rot_kp_index[None]))['total'])
                loss.append(torch.min(torch.stack(loss_rot)))
                best_kp_indexes.append(kp_index[torch.argmin(torch.stack(loss_rot))])
            loss = torch.mean(torch.stack(loss))
            
            geo_dists = [self.geo_dists[mesh_name] for mesh_name in mesh_names]
            input = (pcds.cuda(), torch.stack(best_kp_indexes).cuda(), pred_index, geo_dists)
            corr_list = self.metric(input)
            results_list.append(corr_list)
            
            loss_avg += loss.item()
            cnt += 1

        loss_avg = loss_avg / cnt
        self.writer.add_scalar('test-loss', loss_avg, 0)

        self.fout.write("{}".format(self.cfg.class_name))
        results_list = np.mean(results_list, axis=0)
        for i, corr in enumerate(results_list):
            self.writer.add_scalar('correspondence/{:.2f}'.format(i*0.01), corr, 0)
            log_content = 'pck_{:.2f}: {:.8f}'.format(i*0.01, corr)
            self.fout.write("\t{:.8f}".format(corr))
            self.logger.info(log_content)
        self.fout.write("\n")
        
        self.logger.info("Test loss: {}".format(loss_avg))

