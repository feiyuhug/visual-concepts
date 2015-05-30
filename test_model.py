import caffe
import numpy as np
import cv2
import sg_utils as utils
import cap_eval_utils
from IPython.core.debugger import Tracer
# import caffe

def load_model(prototxt_file, model_file, base_image_size, mean, vocab): 
  """
  Load the model from file. Includes pointers to the prototxt file, 
  caffemodel file name, and other settings - image mean, base_image_size, vocab 
  """
  model = {};
  model['net']= caffe.Net(prototxt_file, model_file, caffe.TEST);
  model['base_image_size'] = base_image_size;
  model['means'] = mean; model['vocab'] = vocab;
  return model



def test_model(imdb, model, detection_file = None):
  """
  Tests model and stores detections on disk
  """
  N_WORDS = len(model['vocab']['words'])
  sc = np.zeros((imdb.num_images, N_WORDS), dtype=np.float)
  mil_prob = np.zeros((imdb.num_images, N_WORDS), dtype=np.float)
  for i in xrange(len(imdb.image_index)):
    im = cv2.imread(imdb.image_path_at(i))
    sc[i,:], mil_prob[i,:] = test_img(im, model['net'], model['base_image_size'], model['means'])

  if detection_file is not None:
    utils.save_variables(detection_file, [sc, mil_prob, model['vocab'], imdb],
      ['sc', 'mil_prob', 'vocab', 'imdb'], overwrite = True)

def benchmark(imdb, vocab, gt_label, num_references, detection_file, eval_file = None):
  # Get ground truth
  # counts = get_vocab_counts(imdb.image_index, coco_caps, max_cap, vocab)
  # dt = utils.scio.loadmat(detection_file)
  dt = utils.load_variables(detection_file)
  mil_prob = dt['mil_prob'];
  
  # Benchmark the output, and return a result struct
  P     = np.zeros(mil_prob.shape, dtype          = np.float)
  R     = np.zeros(mil_prob.shape, dtype          = np.float)
  score = np.zeros(mil_prob.shape, dtype          = np.float)
  ap    = np.zeros((1,len(vocab['words'])), dtype = np.float)
  for i in range(len(vocab['words'])):
    P[:,i], R[:,i], score[:,i], ap[0,i] = cap_eval_utils.calc_pr_ovr(gt_label[:,i], mil_prob[:,i], num_references)
    # print '{:20s}: {:.3f}'.format(vocab['words'][i], ap[0,i]*100) 
  details = {'precision': P, 'recall': R, 'ap': ap, 'score': score}; 
  
  # Collect statistics over the POS
  agg = [];
  for pos in list(set(vocab['poss'])):
    ind = [i for i,x in enumerate(vocab['poss']) if pos == x]
    print "{:5s} [{:4d}] : {:5.2f} {:5.2f} ".format(pos, len(ind), 100*np.mean(ap[0, ind]), 100*np.mean(ap[0, ind]))
    agg.append({'pos': pos, 'ap': 100*np.mean(ap[0, ind])})  
  
  ind = range(len(vocab['words'])); pos = 'all';
  print "{:5s} [{:4d}] : {:5.2f} {:5.2f} ".format(pos, len(ind), 100*np.mean(ap[0, ind]), 100*np.mean(ap[0, ind]))
  agg.append({'pos': 'all', 'ap': 100*np.mean(ap[0, ind])})  

  if eval_file is not None:
    utils.save_variables(eval_file, [details, agg, vocab, imdb],
      ['details', 'agg', 'vocab', 'imdb'], overwrite = True)
  
  return details

def test_img(im, net, base_image_size, means):
  """
  Calls Caffe to get output for this image
  """
  # Resize image
  im_orig = im.astype(np.float32, copy=True)
  im_orig -= means
  
  im, gr, grr = upsample_image(im_orig, base_image_size)
  im = np.transpose(im, axes = (2, 0, 1))
  im = im[np.newaxis, :, :, :]
  
  # Pass into Caffe
  net.forward(data=im.astype(np.float32, copy=False))

  # Get outputs and return them
  mil_prob= net.blobs['mil'].data.copy()
  sc = net.blobs['mil_max'].data.copy()

  # reshape appropriately
  mil_prob = mil_prob.reshape((1, mil_prob.size))
  sc = sc.reshape((1, sc.size))
  return sc, mil_prob


def upsample_image(im, sz):
  h = im.shape[0]
  w = im.shape[1]
  s = max(h, w)
  I_out = np.zeros((sz, sz, 3), dtype = np.float);
  I = cv2.resize(im, None, None, fx = np.float(sz)/s, fy = np.float(sz)/s, interpolation=cv2.INTER_LINEAR); 
  SZ = I.shape;
  I_out[0:I.shape[0], 0:I.shape[1],:] = I;
  return I_out, I, SZ
