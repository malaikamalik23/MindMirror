const ctx = document.getElementById("emotionChart").getContext("2d");

new Chart(ctx, {
  type: "pie",
  data: {
    labels: window.chartData.labels,
    datasets: [{
      label: "Emotions",
      data: window.chartData.data,
      backgroundColor: [
        "#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0",
        "#9966FF", "#FF9F40", "#E7E9ED", "#8B0000"
      ],
    }],
  },
  options: {
    responsive: true,
    plugins: {
      legend: {
        position: "bottom"
      },
      title: {
        display: true,
        text: "Emotion Overview"
      }
    }
  }
});
