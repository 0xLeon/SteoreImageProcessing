import pickle

import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as st

with open('DataFitErrors.pkl', 'rb') as f:
	data = pickle.load(f)

data = data['1280x720']
intervals = np.array([st.t.interval(0.95, len(data[i])-1, loc=np.mean(data[i]), scale=st.sem(data[i])) for i in data])
means = [np.mean(data[i]) for i in data]

print(intervals)

plt.errorbar(data.keys(), means, np.abs(intervals).T, fmt='o-', ecolor='k', elinewidth=0.7, barsabove=True, capsize=2.5)
plt.grid(True)
plt.show()
