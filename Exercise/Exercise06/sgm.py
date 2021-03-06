import argparse
import decimal
import itertools
import multiprocessing
import time

import cv2
import numpy as np

class TimeMeasurement(object):
	def __init__(self, operation, printStd=True):
		self._t0 = 0
		self._t1 = 0

		self._operation = operation
		self._printStd = printStd

	@property
	def delta(self):
		return self._t1 - self._t0

	def __enter__(self):
		self._t1 = 0
		self._t0 = time.perf_counter()

		return self

	def __exit__(self, *args):
		self._t1 = time.perf_counter()

		if self._printStd:
			print('Operation \'{!s}\' took {:.4f} s'.format(self._operation, self.delta))

def pixelCostSimple(v, u, d, imgL, imgR):
	ud = u + d

	if ud >= imgL.shape[1]:
		ud = imgL.shape[1] - 1

	return np.abs(imgL[v, ud] - imgR[v, u])

def pixelCostGithub(row, leftCol, rightCol, imgL, imgR):
	leftValue = 0
	rightValue = 0
	beforeRightValue = 0
	afterRightValue = 0
	rightValueMinus = 0
	rightValuePlus = 0
	rightValueMin = 0
	rightValueMax = 0

	if leftCol >= 0:
		leftValue = imgL[row, leftCol]

	if rightCol >= 0:
		rightValue = imgR[row, rightCol]


	if rightCol > 0:
		beforeRightValue = imgR[row, rightCol - 1]
	else:
		beforeRightValue = rightValue

	if rightCol > 0 and (rightCol + 1) < imgR.shape[1]:
		afterRightValue = imgR[row, rightCol + 1]
	else:
		afterRightValue = rightValue

	rightValueMinus = int(decimal.Decimal((rightValue + beforeRightValue) / 2.0).quantize(0, decimal.ROUND_HALF_UP))
	rightValuePlus = int(decimal.Decimal((rightValue + afterRightValue) / 2.0).quantize(0, decimal.ROUND_HALF_UP))

	rightValueMin = np.min([rightValue, rightValueMinus, rightValuePlus])
	rightValueMax = np.max([rightValue, rightValueMinus, rightValuePlus])

	return np.max([0, leftValue - rightValueMax, rightValueMin - leftValue])

def preCalculateCostsSimple(imgL, imgR, numDisp):
	C = np.empty(imgL.shape + (numDisp,))

	for v in range(imgL.shape[0]):
		for u in range(imgL.shape[1]):
			for d in range(numDisp):
				C[v, u, d] = pixelCostSimple(v, u, d, imgL, imgR)

	return C

def preCalculateCostsGithub(imgL, imgR, numDisp):
	C = np.empty(imgL.shape + (numDisp,))

	for v in range(imgL.shape[0]):
		for u in range(imgL.shape[1]):
			for d in range(numDisp):
				C[v, u, d] = np.min([
					pixelCostGithub(v, u, u - d, imgL, imgR),
					pixelCostGithub(v, u - d, u, imgR, imgL),
				])

	return C

def preCalculateCosts(imgL, imgR, numDisp):
	imgLShifted = imgL.copy()

	C = np.empty(imgL.shape + (numDisp,))
	C[:, :, 0] = np.abs(imgR - imgLShifted)

	for d in range(1, numDisp):
		imgLShifted[:, :-1] = imgLShifted[:, 1:]

		C[:, :, d] = np.abs(imgR - imgLShifted)

	return C

def generatePaths(imgShape, directions=8):
	if directions not in [2**x for x in range(5)]:
		raise ValueError('Invalid number of directions {:d}'.format(directions))

	paths = [
		(np.array([-1, 0]), np.array(list(zip([imgShape[1] - 1] * imgShape[0], range(imgShape[0]))))),
	]

	if directions > 1:
		paths.extend([
			(np.array([1, 0]), np.array(list(zip([0] * imgShape[0], range(imgShape[0]))))),
		])

	if directions > 2:
		paths.extend([
			(np.array([0, -1]), np.array(list(zip(range(imgShape[1]), [imgShape[0] - 1] * imgShape[1])))),
			(np.array([0, 1]), np.array(list(zip(range(imgShape[1]), [0] * imgShape[1])))),
		])

	if directions > 4:
		paths.extend([
			(np.array([-1, -1]), np.vstack((np.array(list(zip(range(imgShape[1]), [imgShape[0] - 1] * imgShape[1]))), np.array(list(zip([imgShape[1] - 1] * (imgShape[0] - 1), range(imgShape[0] - 1))))))),
			(np.array([1, -1]), np.vstack((np.array(list(zip(range(imgShape[1]), [imgShape[0] - 1] * imgShape[1]))), np.array(list(zip([0] * (imgShape[0] - 1), range(imgShape[0] - 1))))))),
			(np.array([1, 1]), np.vstack((np.array(list(zip(range(imgShape[1]), [0] * imgShape[1]))), np.array(list(zip([0] * (imgShape[0] - 1), range(1, imgShape[0]))))))),
			(np.array([-1, 1]), np.vstack((np.array(list(zip(range(imgShape[1]), [0] * imgShape[1]))), np.array(list(zip([imgShape[1] - 1] * (imgShape[0] - 1), range(1, imgShape[0]))))))),
		])

	if directions > 8:
		paths.extend([
			(np.array([-2, -1]), np.vstack((np.array(list(zip(range(imgShape[1]), [imgShape[0] - 1] * imgShape[1]))), np.array(list(zip(([imgShape[1] - 1] * (imgShape[0] - 1)) + ([imgShape[1] - 2] * (imgShape[0] - 1)), list(range(imgShape[0] - 1)) * 2)))))),
			(np.array([-1, -2]), np.vstack((np.array(list(zip(list(range(imgShape[1])) * 2, ([imgShape[0] - 1] * imgShape[1]) + ([imgShape[0] - 2] * imgShape[1])))), np.array(list(zip([imgShape[1] - 1] * (imgShape[0] - 2), range(imgShape[0] - 2))))))),
			(np.array([1, -2]), np.vstack((np.array(list(zip(list(range(imgShape[1])) * 2, ([imgShape[0] - 1] * imgShape[1]) + ([imgShape[0] - 2] * imgShape[1])))), np.array(list(zip([0] * (imgShape[0] - 2), range(imgShape[0] - 2))))))),
			(np.array([2, -1]), np.vstack((np.array(list(zip(range(imgShape[1]), [imgShape[0] - 1] * imgShape[1]))), np.array(list(zip(([0] * (imgShape[0] - 1)) + ([1] * (imgShape[0] - 1)), list(range(imgShape[0] - 1)) * 2)))))),
			(np.array([2, 1]), np.vstack((np.array(list(zip(range(imgShape[1]), [0] * imgShape[1]))), np.array(list(zip(([0] * (imgShape[0] - 1)) + ([1] * (imgShape[0] - 1)), list(range(1, imgShape[0])) * 2)))))),
			(np.array([1, 2]), np.vstack((np.array(list(zip(list(range(imgShape[1])) * 2, ([0] * imgShape[1]) + ([1] * imgShape[1])))), np.array(list(zip([0] * (imgShape[0] - 2), range(2, imgShape[0]))))))),
			(np.array([-1, 2]), np.vstack((np.array(list(zip(list(range(imgShape[1])) * 2, ([0] * imgShape[1]) + ([1] * imgShape[1])))), np.array(list(zip([imgShape[1] - 1] * (imgShape[0] - 2), range(2, imgShape[0]))))))),
			(np.array([-2, 1]), np.vstack((np.array(list(zip(range(imgShape[1]), [0] * imgShape[1]))), np.array(list(zip(([imgShape[1] - 1] * (imgShape[0] - 1)) + ([imgShape[1] - 2] * (imgShape[0] - 1)), list(range(1, imgShape[0])) * 2)))))),
		])

	return paths

def _sgm_inner(direction, C, numDisp, p1, p2):
	p = direction[1]

	Lr = np.zeros_like(C)
	Lr[p[:, 1], p[:, 0], :] += C[p[:, 1], p[:, 0], :]

	p += direction[0]
	p = p[(p[:, 0] > -1) & (p[:, 0] < C.shape[1]) & (p[:, 1] > -1) & (p[:, 1] < C.shape[0])]

	while p.size > 0:
		prev = p - direction[0]
		minPrevD = Lr[prev[:, 1], prev[:, 0], :].min(axis=1)

		for d in range(numDisp):
			dPrev = d - 1
			dNext = d + 1

			if dPrev < 0:
				dPrev = d
			elif dNext >= numDisp:
				dNext = d

			Lr[p[:, 1], p[:, 0], d] = C[p[:, 1], p[:, 0], d] + np.amin([
				Lr[prev[:, 1], prev[:, 0], d],
				Lr[prev[:, 1], prev[:, 0], dPrev] + p1,
				Lr[prev[:, 1], prev[:, 0], dNext] + p1,
				minPrevD + p2,
			], axis=0) - minPrevD

		p += direction[0]
		p = p[(p[:, 0] > -1) & (p[:, 0] < C.shape[1]) & (p[:, 1] > -1) & (p[:, 1] < C.shape[0])]

	return Lr

def sgm(imgL, imgR, p1, p2, disparityRange, directions=8, parallel=True):
	imgL = imgL.astype(np.float)
	imgR = imgR.astype(np.float)

	dispRange = range(disparityRange[0], disparityRange[1] + 1)
	numDisp = len(dispRange)

	with TimeMeasurement('Generate paths'):
		paths = generatePaths(imgL.shape, directions)

	with TimeMeasurement('Pre-calculate costs'):
		C = preCalculateCosts(imgL, imgR, numDisp)

	if directions > 1:
		if parallel:
			workPackages = zip(
				paths,
				itertools.repeat(C),
				itertools.repeat(numDisp),
				itertools.repeat(p1),
				itertools.repeat(p2),
			)

			with multiprocessing.Pool(min(multiprocessing.cpu_count(), directions)) as pool:
				Lr = pool.starmap(_sgm_inner, workPackages)
		else:
			Lr = np.zeros((directions,) + C.shape)

			for i, direction in enumerate(paths):
				Lr[i, :, :, :] += _sgm_inner(direction, C, numDisp, p1, p2)

		S = np.sum(Lr, axis=0)
	else:
		S = _sgm_inner(paths[0], C, numDisp, p1, p2)

	dispImage = S.argmin(axis=2)

	return dispImage

def main(imgLPath, imgRPath, p1, p2, disparityRange, directions=8, outputPath='depth.png', parallel=True):
	imgL = cv2.imread(imgLPath)
	imgR = cv2.imread(imgRPath)

	if imgL is None:
		raise ValueError('Image file {:s} not readable or not an image'.format(imgLPath))

	if imgR is None:
		raise ValueError('Image file {:s} not readable or not an image'.format(imgRPath))

	imgL = cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY)
	imgR = cv2.cvtColor(imgR, cv2.COLOR_BGR2GRAY)

	print('Calculating disparity map with SGM using {:d} directions'.format(directions))

	with TimeMeasurement('SGM{:s}'.format(' Parallel' if parallel else '')):
		dispImage = sgm(imgL, imgR, p1, p2, disparityRange, directions, parallel)

	dispImage = ((dispImage.astype(np.float) / dispImage.max()) * np.iinfo(np.uint16).max).astype(np.uint16)
	cv2.imwrite(outputPath, dispImage)

def main_example():
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 1, 'depth.01.lin.png', False)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 1, 'depth.01.par.png', True)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 2, 'depth.02.lin.png', False)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 2, 'depth.02.par.png', True)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 4, 'depth.04.lin.png', False)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 4, 'depth.04.par.png', True)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 8, 'depth.08.lin.png', False)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 8, 'depth.08.par.png', True)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 16, 'depth.16.lin.png', False)
	print('')
	main('tsukuba_l.png', 'tsukuba_r.png', 8, 32, (0, 20), 16, 'depth.16.par.png', True)

def main_cli(args=None):
	parser = argparse.ArgumentParser()
	parser.add_argument('--output', default='./depth.png')
	parser.add_argument('--p1', type=int, default=8)
	parser.add_argument('--p2', type=int, default=32)
	parser.add_argument('--directions', type=int, default=8, choices=[1, 2, 4, 8, 16])
	parser.add_argument('--disparityrange', default='0,20')
	parser.add_argument('--examples', default=False, action='store_true')
	parser.add_argument('images', default=['tsukuba_l.png', 'tsukuba_r.png'], nargs='*')
	args = parser.parse_args(args)

	if args.examples:
		return main_example()

	if len(args.images) != 2:
		parser.error('Specifiy exactly two images!')

	disparityrange = tuple(map(int, args.disparityrange.split(',')))

	main(args.images[0], args.images[1], args.p1, args.p2, disparityrange, args.directions, args.output)

if __name__ == '__main__':
	main_cli()
