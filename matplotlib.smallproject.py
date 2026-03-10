# ipl carrer of abhishek sharma 
import matplotlib.pyplot as plt


year = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]#years of ipl career of abhishek sharma
run  = [63, 9, 71, 98, 426, 226, 484, 439] #runs scored by abhishek sharma in each year of his ipl career

# Stack plot (single data series)
plt.stackplot(year, run, labels=['Runs'], colors=['orange'])
plt.title("Abhishek Sharma Runs per Year")
plt.xlabel("Year")
plt.ylabel("Runs")
plt.legend(loc='upper left')
plt.show()
