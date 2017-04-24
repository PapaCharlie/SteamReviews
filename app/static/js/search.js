$(document).ready(function () {
	$(".details-close").click(function() {
		$(".details-content-wrapper").fadeOut(100, function() {
			$(".details-overlay").animate({width:'0px'}, 300);
		});
	});

	$(".result-box").click(function() {
		var resultBox = $(this);
		$(".details-title").text(resultBox.data("title"));
		$(".details-img").attr("src", resultBox.children(".result-img").attr("src"));
		$(".details-link").attr("href", resultBox.data("steam-url"));

		var tags = resultBox.data("tags");
		var tags_keys = [];
		var tags_values = [];
		for (var key in tags) {
	    if (!tags.hasOwnProperty(key)) continue;
	    tags_keys.push(key);
	    tags_values.push(tags[key]);
	  }
		var data = {
		    labels: tags_keys,
		    datasets: [
		        {
		            label: "Game tags",
		            backgroundColor: "rgba(255,99,132,0.2)",
		            borderColor: "rgba(255,99,132,1)",
		            pointBackgroundColor: "rgba(255,99,132,1)",
		            pointBorderColor: "#fff",
		            pointHoverBackgroundColor: "#fff",
		            pointHoverBorderColor: "rgba(255,99,132,1)",
		            data: tags_values
		        }
		    ]
		};

		var attributeChart = $(".details-attribute-chart");
		var myRadarChart = new Chart(attributeChart, {
			type: 'radar',
		    data: data,
		    options: {
		    	legend: {
		    		display: false
		    	},
		    	scale: {
			        ticks: {
			            display: false
			        }
			    },
			    tooltips: {
			    	enabled: false
			    }
		    }
		});

		$(".details-overlay").animate({width:'40%'}, 300, function() {
			$(".details-content-wrapper").fadeIn(100);
		});
	});
});
